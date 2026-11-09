"""
Server-authoritative betting and settlement.

Money flow (all virtual credits, double-entry where wallets exchange value):

  place bet   player.available -> player.reserved          (stake is held)
  LOST        player.reserved  -> PLATFORM RESERVE          (stake)
  CASHED_OUT  player.reserved  -> player.available          (stake back)
              winnings source -> player wallet              (profit)
  VOID        player.reserved  -> player.available          (round aborted)

The winnings source is the respective major account's wallet by default
(settings.GAME_WINNINGS_SOURCE = "MAJOR_ACCOUNT"); set it to
"PLATFORM_RESERVE" to have the platform reserve pay winnings instead.

The multiplier used for a cash-out is always computed on the server from
the round's own clock. The client never supplies a multiplier or an amount
to pay out.
"""

from decimal import Decimal, ROUND_DOWN

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from game.models import GameRound, PlayerBet
from game.services.round_service import get_display_multiplier
from tenants.models import MajorAccount, PlayerSlot
from wallets.models import LedgerEntry, LedgerTransaction, Wallet

CENT = Decimal("0.01")
MAX_BALANCE = Decimal("10000000000000000")


class BetError(Exception):
    """A rule was broken; `status` is the HTTP status the API should use."""

    def __init__(self, detail, status=409):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def _latest_round_locked():
    return (
        GameRound.objects.select_for_update()
        .order_by("-round_number")
        .first()
    )


def _lock_wallets(player_slot, major_account):
    """
    Lock the player, major-account and platform-reserve wallets in a
    consistent (id) order. Returns (player, major, reserve).

    The platform reserve wallet is created if it does not exist yet, so a
    missing reserve can never block a round from crashing.
    """
    player_id = (
        Wallet.objects.filter(player_slot=player_slot)
        .values_list("id", flat=True)
        .first()
    )
    major_id = (
        Wallet.objects.filter(major_account=major_account)
        .values_list("id", flat=True)
        .first()
    )

    if player_id is None or major_id is None:
        raise BetError("A required wallet is missing.")

    reserve_id = (
        Wallet.objects.filter(platform_reserve=True)
        .values_list("id", flat=True)
        .first()
    )

    if reserve_id is None:
        reserve_id = Wallet.objects.get_or_create(platform_reserve=True)[0].id

    locked = {
        w.id: w
        for w in Wallet.objects.select_for_update()
        .filter(id__in=[player_id, major_id, reserve_id])
        .order_by("id")
    }
    return locked[player_id], locked[major_id], locked[reserve_id]


def _record_transfer(*, bet, source, destination, amount, description):
    """Create one balanced ledger transaction and link it to the bet."""
    ledger_transaction = LedgerTransaction.objects.create(
        idempotency_key=f"bet-settle:{bet.id}",
        transaction_type=LedgerTransaction.TransactionType.SETTLEMENT,
        description=description[:255],
        created_by=bet.major_account.owner,
    )
    LedgerEntry.objects.create(
        transaction=ledger_transaction,
        wallet=source,
        direction=LedgerEntry.Direction.DEBIT,
        amount=amount,
    )
    LedgerEntry.objects.create(
        transaction=ledger_transaction,
        wallet=destination,
        direction=LedgerEntry.Direction.CREDIT,
        amount=amount,
    )
    bet.settlement_transaction = ledger_transaction


def _settle(bet, outcome, multiplier=None):
    """
    Settle one PLACED bet. The caller must hold the round lock inside a
    transaction.

    A lost stake goes to the platform reserve. Winnings are paid by the
    configured winnings source (the major account by default).
    """
    player_wallet, major_wallet, reserve_wallet = _lock_wallets(
        bet.player_slot, bet.major_account
    )
    stake = bet.stake
    label = (
        f"Round {bet.game_round.round_number}, "
        f"Player {bet.player_slot.slot_number}"
    )
    touched = {player_wallet.id: player_wallet}

    player_wallet.reserved_balance -= stake

    if outcome == PlayerBet.Status.LOST:
        # No cash-out before the crash: the stake returns to the platform
        # reserve (not to the major account).
        _record_transfer(
            bet=bet,
            source=player_wallet,
            destination=reserve_wallet,
            amount=stake,
            description=f"{label}: bet lost, stake to platform reserve",
        )
        reserve_wallet.available_balance += stake
        touched[reserve_wallet.id] = reserve_wallet
        bet.payout = Decimal("0.00")

    elif outcome == PlayerBet.Status.CASHED_OUT:
        payout = (stake * multiplier).quantize(CENT, rounding=ROUND_DOWN)
        profit = max(payout - stake, Decimal("0.00"))

        source = (
            reserve_wallet
            if getattr(settings, "GAME_WINNINGS_SOURCE", "PLATFORM_RESERVE")
            == "PLATFORM_RESERVE"
            else major_wallet
        )
        paid = min(profit, source.available_balance)

        player_wallet.available_balance += stake

        if paid > 0:
            _record_transfer(
                bet=bet,
                source=source,
                destination=player_wallet,
                amount=paid,
                description=f"{label}: cashed out at {multiplier}x",
            )
            source.available_balance -= paid
            player_wallet.available_balance += paid
            touched[source.id] = source

        bet.cashout_multiplier = multiplier
        bet.payout = stake + paid
        bet.payout_capped = paid < profit

    elif outcome == PlayerBet.Status.VOID:
        player_wallet.available_balance += stake
        bet.payout = stake

    else:
        raise ValueError("Unknown settlement outcome.")

    for wallet in touched.values():
        wallet.save(
            update_fields=[
                "available_balance",
                "reserved_balance",
                "updated_at",
            ]
        )

    bet.status = outcome
    bet.settled_at = timezone.now()
    bet.save(
        update_fields=[
            "status",
            "cashout_multiplier",
            "payout",
            "payout_capped",
            "settlement_transaction",
            "settled_at",
        ]
    )
    return bet


@transaction.atomic
def place_bet(*, major_account_id, slot_number, stake):
    """Place a bet for a player slot on the round that is waiting to start."""
    game_round = _latest_round_locked()

    if game_round is None or game_round.status != GameRound.Status.WAITING:
        raise BetError(
            "Bets are accepted only while a round is waiting to start."
        )

    account = MajorAccount.objects.filter(pk=major_account_id).first()

    if account is None or account.status != MajorAccount.Status.ACTIVE:
        raise BetError("Major account is not active.")

    slot = PlayerSlot.objects.filter(
        major_account=account,
        slot_number=slot_number,
    ).first()

    if slot is None:
        raise BetError("Player slot not found.", status=404)

    if slot.status != PlayerSlot.Status.ACTIVE:
        raise BetError("Only active player slots can place bets.")

    if PlayerBet.objects.filter(
        game_round=game_round, player_slot=slot
    ).exists():
        raise BetError("This player already has a bet in this round.")

    player_wallet, _major, _reserve = _lock_wallets(slot, account)

    if player_wallet.available_balance < stake:
        raise BetError("Insufficient available virtual credits.")

    player_wallet.available_balance -= stake
    player_wallet.reserved_balance += stake
    player_wallet.save(
        update_fields=["available_balance", "reserved_balance", "updated_at"]
    )

    return PlayerBet.objects.create(
        game_round=game_round,
        player_slot=slot,
        major_account=account,
        stake=stake,
    )


@transaction.atomic
def cash_out(*, major_account_id, slot_number):
    """Exit the running round at the server's current multiplier."""
    game_round = _latest_round_locked()

    if game_round is None or game_round.status != GameRound.Status.RUNNING:
        raise BetError("There is no round in flight to cash out of.")

    bet = (
        PlayerBet.objects.select_for_update()
        .select_related("game_round", "player_slot", "major_account__owner")
        .filter(
            game_round=game_round,
            major_account_id=major_account_id,
            player_slot__slot_number=slot_number,
        )
        .first()
    )

    if bet is None:
        raise BetError("This player has no bet in the current round.", 404)

    if bet.status != PlayerBet.Status.PLACED:
        raise BetError("This bet has already been settled.")

    multiplier = get_display_multiplier(game_round)

    if multiplier >= game_round.final_multiplier:
        raise BetError("The round has already crashed.")

    return _settle(bet, PlayerBet.Status.CASHED_OUT, multiplier)


def settle_crashed_round(game_round):
    """Every bet still PLACED when a round crashes is lost."""
    bets = (
        PlayerBet.objects.select_for_update()
        .select_related("game_round", "player_slot", "major_account__owner")
        .filter(game_round=game_round, status=PlayerBet.Status.PLACED)
        .order_by("created_at")
    )
    for bet in bets:
        _settle(bet, PlayerBet.Status.LOST)


def void_round_bets(game_round):
    """Refund every unsettled bet of an aborted round."""
    bets = (
        PlayerBet.objects.select_for_update()
        .select_related("game_round", "player_slot", "major_account__owner")
        .filter(game_round=game_round, status=PlayerBet.Status.PLACED)
        .order_by("created_at")
    )
    for bet in bets:
        _settle(bet, PlayerBet.Status.VOID)
