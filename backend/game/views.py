
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.authentication import DeviceCredentialAuthentication
from game.models import GameEngineHeartbeat, GameRound
from game.services.round_service import get_display_multiplier


class CurrentGameRoundView(APIView):
    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        game_round = (
            GameRound.objects
            .order_by("-round_number")
            .first()
        )

        if game_round is None:
            return Response({
                "round": None,
                "detail": "No game round has been created yet.",
            })

        multiplier = get_display_multiplier(game_round)

        # Reveal the final result only after the round has crashed.
        reveal_final = game_round.status in (
            GameRound.Status.CRASHED,
            GameRound.Status.COMPLETED,
        )

        return Response({
            "round": {
                "id": str(game_round.id),
                "round_number": game_round.round_number,
                "status": game_round.status,
                "scheduled_start_at": (
                    game_round.scheduled_start_at.isoformat()
                    if game_round.scheduled_start_at else None
                ),
                "started_at": (
                    game_round.started_at.isoformat()
                    if game_round.started_at else None
                ),
                "crashed_at": (
                    game_round.crashed_at.isoformat()
                    if game_round.crashed_at else None
                ),
                "display_multiplier": (
                    str(multiplier)
                    if multiplier is not None else None
                ),
                "final_multiplier": (
                    str(game_round.final_multiplier)
                    if reveal_final
                    and game_round.final_multiplier is not None
                    else None
                ),
            }
        })


from datetime import timedelta

from django.utils import timezone


class GameEngineHealthView(APIView):
    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        heartbeat = GameEngineHeartbeat.objects.filter(pk=1).first()

        if heartbeat is None:
            return Response(
                {
                    "healthy": False,
                    "status": "UNKNOWN",
                    "detail": "No engine heartbeat has been recorded.",
                },
                status=503,
            )

        heartbeat_is_fresh = (
            timezone.now() - heartbeat.last_heartbeat_at
            <= timedelta(seconds=10)
        )

        healthy = heartbeat.is_running and heartbeat_is_fresh

        return Response({
            "healthy": healthy,
            "status": "RUNNING" if healthy else "UNAVAILABLE",
            "last_heartbeat_at": heartbeat.last_heartbeat_at.isoformat(),
        }, status=200 if healthy else 503)


# ---------------------------------------------------------------------------
# Betting
# ---------------------------------------------------------------------------

from django.db import IntegrityError

from game.models import PlayerBet
from game.services.bet_service import BetError, cash_out, place_bet
from wallets.models import Wallet
from wallets.views import parse_positive_amount


def serialize_bet(bet):
    return {
        "id": str(bet.id),
        "round_id": str(bet.game_round_id),
        "round_number": bet.game_round.round_number,
        "slot_number": bet.player_slot.slot_number,
        "stake": str(bet.stake),
        "status": bet.status,
        "cashout_multiplier": (
            str(bet.cashout_multiplier)
            if bet.cashout_multiplier is not None else None
        ),
        "payout": str(bet.payout) if bet.payout is not None else None,
        "payout_capped": bet.payout_capped,
    }


def balances_for(bet):
    """Wallet balances after an action, so the client never has to guess."""
    player_wallet = Wallet.objects.get(player_slot_id=bet.player_slot_id)
    major_wallet = Wallet.objects.get(major_account_id=bet.major_account_id)
    reserve_wallet = Wallet.objects.filter(platform_reserve=True).first()
    return {
        "player_balance": str(player_wallet.available_balance),
        "major_account_balance": str(major_wallet.available_balance),
        "platform_reserve_balance": str(
            reserve_wallet.available_balance if reserve_wallet else "0.00"
        ),
    }


def parse_slot_number(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw if 1 <= raw <= 8 else None


class PlaceBetView(APIView):
    """Place a bet for a player slot on the round that is waiting to start."""

    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        slot_number = parse_slot_number(request.data.get("slot_number"))
        amount = parse_positive_amount(request.data.get("amount"))

        if slot_number is None:
            return Response(
                {"detail": "slot_number must be an integer from 1 to 8."},
                status=400,
            )

        if amount is None:
            return Response(
                {
                    "detail": (
                        "amount must be positive, with at most "
                        "2 decimal places."
                    )
                },
                status=400,
            )

        # The account always comes from the authenticated installation.
        installation = request.auth

        try:
            bet = place_bet(
                major_account_id=installation.major_account_id,
                slot_number=slot_number,
                stake=amount,
            )
        except BetError as exc:
            return Response({"detail": exc.detail}, status=exc.status)
        except IntegrityError:
            return Response(
                {"detail": "This player already has a bet in this round."},
                status=409,
            )

        return Response(
            {"bet": serialize_bet(bet), **balances_for(bet)},
            status=201,
        )


class CashOutBetView(APIView):
    """Exit the running round. The server decides the multiplier."""

    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        slot_number = parse_slot_number(request.data.get("slot_number"))

        if slot_number is None:
            return Response(
                {"detail": "slot_number must be an integer from 1 to 8."},
                status=400,
            )

        installation = request.auth

        try:
            bet = cash_out(
                major_account_id=installation.major_account_id,
                slot_number=slot_number,
            )
        except BetError as exc:
            return Response({"detail": exc.detail}, status=exc.status)

        return Response(
            {"bet": serialize_bet(bet), **balances_for(bet)},
            status=200,
        )


class CurrentBetsView(APIView):
    """
    Bets of this installation's major account for the latest round and
    the one before it (so a result stays visible after the next round starts).
    """

    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        installation = request.auth

        latest = GameRound.objects.order_by("-round_number").first()

        if latest is None:
            return Response({"bets": []})

        bets = (
            PlayerBet.objects
            .select_related("game_round", "player_slot")
            .filter(
                major_account_id=installation.major_account_id,
                game_round__round_number__gte=latest.round_number - 1,
            )
            .order_by("game_round__round_number", "player_slot__slot_number")
        )

        return Response({"bets": [serialize_bet(bet) for bet in bets]})


# ---------------------------------------------------------------------------
# Jackpots
# ---------------------------------------------------------------------------

from game.models import Jackpot


class JackpotListView(APIView):
    """Active jackpots for the game client's jackpot bar."""

    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jackpots = Jackpot.objects.filter(is_active=True).order_by(
            "sort_order", "code"
        )

        return Response(
            {
                "jackpots": [
                    {
                        "id": jackpot.code,
                        "label": jackpot.label,
                        "amount": str(jackpot.amount),
                        "color": jackpot.color,
                        "icon": jackpot.icon,
                    }
                    for jackpot in jackpots
                ]
            }
        )
