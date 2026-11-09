import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from devices.models import DeviceInstallation
from game.models import GameRound, PlayerBet
from game.services.bet_service import BetError, cash_out, place_bet
from game.services.round_service import (
    complete_round,
    create_waiting_round,
    crash_round,
    recover_interrupted_rounds,
    start_round,
)
from tenants.models import MajorAccount, PlayerSlot
from wallets.models import LedgerEntry, LedgerTransaction, Wallet

D = Decimal


class BettingSettlementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="TestOnlyPassword123!",
            role=User.Role.MAJOR_OWNER,
        )
        self.account = MajorAccount.objects.create(
            name="Mwea Arcade", owner=self.owner
        )
        self.major_wallet = Wallet.objects.create(
            major_account=self.account, available_balance=D("1000.00")
        )
        self.slot = PlayerSlot.objects.create(
            major_account=self.account,
            slot_number=1,
            status=PlayerSlot.Status.ACTIVE,
            display_name="Player 1",
        )
        self.player_wallet = Wallet.objects.create(
            player_slot=self.slot, available_balance=D("100.00")
        )
        self.reserve_wallet = Wallet.objects.create(
            platform_reserve=True, available_balance=D("5000.00")
        )

    def balances(self):
        """(player available, player reserved, major account, platform reserve)"""
        self.player_wallet.refresh_from_db()
        self.major_wallet.refresh_from_db()
        self.reserve_wallet.refresh_from_db()
        return (
            self.player_wallet.available_balance,
            self.player_wallet.reserved_balance,
            self.major_wallet.available_balance,
            self.reserve_wallet.available_balance,
        )

    def waiting_round(self, crash_at="2.0000"):
        game_round = create_waiting_round()
        game_round.final_multiplier = D(crash_at)
        game_round.save(update_fields=["final_multiplier"])
        return game_round

    def place(self, amount="10.00"):
        return place_bet(
            major_account_id=self.account.id,
            slot_number=1,
            stake=D(amount),
        )

    # -- placing ---------------------------------------------------------

    def test_placing_a_bet_holds_the_stake(self):
        self.waiting_round()
        bet = self.place("10.00")

        self.assertEqual(bet.status, PlayerBet.Status.PLACED)
        self.assertEqual(
            self.balances(), (D("90.00"), D("10.00"), D("1000.00"), D("5000.00"))
        )

    def test_cannot_bet_more_than_available_balance(self):
        self.waiting_round()
        with self.assertRaises(BetError):
            self.place("100.01")
        self.assertEqual(
            self.balances(), (D("100.00"), D("0.00"), D("1000.00"), D("5000.00"))
        )

    def test_one_bet_per_player_per_round(self):
        self.waiting_round()
        self.place("10.00")
        with self.assertRaises(BetError):
            self.place("5.00")

    def test_bets_only_while_round_is_waiting(self):
        game_round = self.waiting_round()
        start_round(game_round.id)
        with self.assertRaises(BetError):
            self.place("10.00")

    # -- losing ----------------------------------------------------------

    def test_lost_bet_stake_goes_to_platform_reserve_not_major_account(self):
        game_round = self.waiting_round()
        bet = self.place("10.00")
        start_round(game_round.id)
        crash_round(game_round.id)

        bet.refresh_from_db()
        self.assertEqual(bet.status, PlayerBet.Status.LOST)
        # Major account untouched; the reserve receives the stake.
        self.assertEqual(
            self.balances(),
            (D("90.00"), D("0.00"), D("1000.00"), D("5010.00")),
        )

        entries = list(
            LedgerEntry.objects.filter(transaction=bet.settlement_transaction)
        )
        self.assertEqual(len(entries), 2)
        debit = next(e for e in entries if e.direction == "DEBIT")
        credit = next(e for e in entries if e.direction == "CREDIT")
        self.assertEqual(debit.wallet_id, self.player_wallet.id)
        self.assertEqual(credit.wallet_id, self.reserve_wallet.id)
        self.assertEqual(debit.amount, credit.amount)

    def test_missing_reserve_wallet_is_created_so_crash_never_stalls(self):
        self.reserve_wallet.delete()
        game_round = self.waiting_round()
        self.place("10.00")
        start_round(game_round.id)
        crash_round(game_round.id)

        reserve = Wallet.objects.get(platform_reserve=True)
        self.assertEqual(reserve.available_balance, D("10.00"))

    # -- cashing out -----------------------------------------------------

    def test_cash_out_pays_stake_times_server_multiplier(self):
        game_round = self.waiting_round("5.0000")
        bet = self.place("10.00")
        start_round(game_round.id)

        with patch(
            "game.services.bet_service.get_display_multiplier",
            return_value=D("2.5000"),
        ):
            bet = cash_out(major_account_id=self.account.id, slot_number=1)

        self.assertEqual(bet.status, PlayerBet.Status.CASHED_OUT)
        self.assertEqual(bet.payout, D("25.00"))
        # Player: 90 + 25. Major pays the 15.00 profit.
        self.assertEqual(
            self.balances(), (D("115.00"), D("0.00"), D("985.00"), D("5000.00"))
        )

        # Crash afterwards must not touch the settled bet.
        crash_round(game_round.id)
        self.assertEqual(
            self.balances(), (D("115.00"), D("0.00"), D("985.00"), D("5000.00"))
        )

    def test_cash_out_after_crash_point_is_rejected(self):
        game_round = self.waiting_round("2.0000")
        self.place("10.00")
        start_round(game_round.id)

        with patch(
            "game.services.bet_service.get_display_multiplier",
            return_value=D("2.0000"),
        ):
            with self.assertRaises(BetError):
                cash_out(major_account_id=self.account.id, slot_number=1)

    def test_profit_is_capped_by_major_account_balance(self):
        self.major_wallet.available_balance = D("5.00")
        self.major_wallet.save()

        game_round = self.waiting_round("5.0000")
        self.place("10.00")
        start_round(game_round.id)

        with patch(
            "game.services.bet_service.get_display_multiplier",
            return_value=D("3.0000"),
        ):
            bet = cash_out(major_account_id=self.account.id, slot_number=1)

        self.assertTrue(bet.payout_capped)
        self.assertEqual(bet.payout, D("15.00"))
        self.assertEqual(
            self.balances(), (D("105.00"), D("0.00"), D("0.00"), D("5000.00"))
        )

    @override_settings(GAME_WINNINGS_SOURCE="PLATFORM_RESERVE")
    def test_winnings_can_be_paid_by_platform_reserve(self):
        game_round = self.waiting_round("5.0000")
        self.place("10.00")
        start_round(game_round.id)

        with patch(
            "game.services.bet_service.get_display_multiplier",
            return_value=D("2.0000"),
        ):
            cash_out(major_account_id=self.account.id, slot_number=1)

        self.assertEqual(
            self.balances(),
            (D("110.00"), D("0.00"), D("1000.00"), D("4990.00")),
        )

    def test_total_credits_are_conserved(self):
        game_round = self.waiting_round("5.0000")
        self.place("10.00")
        start_round(game_round.id)
        with patch(
            "game.services.bet_service.get_display_multiplier",
            return_value=D("1.7300"),
        ):
            cash_out(major_account_id=self.account.id, slot_number=1)

        self.assertEqual(sum(self.balances()), D("6100.00"))

    # -- aborted rounds --------------------------------------------------

    def test_aborted_round_refunds_the_stake(self):
        self.waiting_round()
        bet = self.place("10.00")
        recover_interrupted_rounds()

        bet.refresh_from_db()
        self.assertEqual(bet.status, PlayerBet.Status.VOID)
        self.assertEqual(
            self.balances(), (D("100.00"), D("0.00"), D("1000.00"), D("5000.00"))
        )


class BettingApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner2",
            password="TestOnlyPassword123!",
            role=User.Role.MAJOR_OWNER,
        )
        self.account = MajorAccount.objects.create(
            name="Kirinyaga Arcade", owner=self.owner
        )
        Wallet.objects.create(
            major_account=self.account, available_balance=D("500.00")
        )
        Wallet.objects.create(
            platform_reserve=True, available_balance=D("2000.00")
        )
        self.slot = PlayerSlot.objects.create(
            major_account=self.account,
            slot_number=2,
            status=PlayerSlot.Status.ACTIVE,
        )
        Wallet.objects.create(
            player_slot=self.slot, available_balance=D("50.00")
        )
        self.credential = "test-device-credential"
        DeviceInstallation.objects.create(
            major_account=self.account,
            installation_id=uuid.uuid4(),
            credential_hash=hashlib.sha256(
                self.credential.encode()
            ).hexdigest(),
        )
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Device {self.credential}"
        )

    def test_place_then_lose_sends_stake_to_platform_reserve(self):
        game_round = create_waiting_round()

        response = self.client.post(
            "/api/game/bets/",
            {"slot_number": 2, "amount": "20.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["player_balance"], "30.00")

        start_round(game_round.id)
        crash_round(game_round.id)

        response = self.client.get("/api/game/bets/current/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bets"][0]["status"], "LOST")

        major = Wallet.objects.get(major_account=self.account)
        reserve = Wallet.objects.get(platform_reserve=True)
        self.assertEqual(major.available_balance, D("500.00"))
        self.assertEqual(reserve.available_balance, D("2020.00"))

        players = self.client.get("/api/devices/player-slots/")
        self.assertEqual(
            players.data["players"][0]["wallet_balance"], "30.00"
        )

    def test_rejects_bad_input_and_unauthenticated_calls(self):
        create_waiting_round()

        for payload in (
            {"slot_number": 9, "amount": "5.00"},
            {"slot_number": "2", "amount": "5.00"},
            {"slot_number": 2, "amount": "-5"},
            {"slot_number": 2, "amount": "5.001"},
            {"slot_number": 2},
        ):
            response = self.client.post(
                "/api/game/bets/", payload, format="json"
            )
            self.assertEqual(response.status_code, 400, payload)

        anonymous = APIClient().post(
            "/api/game/bets/",
            {"slot_number": 2, "amount": "5.00"},
            format="json",
        )
        self.assertIn(anonymous.status_code, (401, 403))
