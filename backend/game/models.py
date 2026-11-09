
import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class GameRound(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        RUNNING = "RUNNING", "Running"
        CRASHED = "CRASHED", "Crashed"
        COMPLETED = "COMPLETED", "Completed"
        ABORTED = "ABORTED", "Aborted"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    round_number = models.PositiveBigIntegerField(unique=True)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.WAITING,
        db_index=True,
    )

    scheduled_start_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    crashed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    final_multiplier = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-round_number"]

    def __str__(self):
        return f"Round {self.round_number} ({self.status})"


class GameEngineHeartbeat(models.Model):
    # One shared heartbeat record for the game engine.
    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )

    last_heartbeat_at = models.DateTimeField()
    is_running = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "running" if self.is_running else "stopped"
        return f"Game engine: {status}"



class PlayerBet(models.Model):
    """
    One bet by one player slot in one round.

    The stake is held in the player wallet's reserved_balance from the
    moment the bet is placed. When the round settles, the result is moved
    between the player wallet and the owning major account's wallet.
    """

    class Status(models.TextChoices):
        PLACED = "PLACED", "Placed"
        CASHED_OUT = "CASHED_OUT", "Cashed out"
        LOST = "LOST", "Lost"
        VOID = "VOID", "Void (round aborted)"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    game_round = models.ForeignKey(
        GameRound,
        on_delete=models.PROTECT,
        related_name="bets",
    )

    player_slot = models.ForeignKey(
        "tenants.PlayerSlot",
        on_delete=models.PROTECT,
        related_name="bets",
    )

    major_account = models.ForeignKey(
        "tenants.MajorAccount",
        on_delete=models.PROTECT,
        related_name="player_bets",
    )

    stake = models.DecimalField(max_digits=18, decimal_places=2)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PLACED,
        db_index=True,
    )

    # Multiplier the player exited at (server time), set on cash-out.
    cashout_multiplier = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )

    # Total returned to the player (stake + profit). 0 for a lost bet.
    payout = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # True when the major account wallet could not cover the full profit.
    payout_capped = models.BooleanField(default=False)

    settlement_transaction = models.OneToOneField(
        "wallets.LedgerTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="player_bet",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game_round", "player_slot"],
                name="one_bet_per_slot_per_round",
            ),
            models.CheckConstraint(
                condition=models.Q(stake__gt=0),
                name="player_bet_stake_positive",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.player_slot} - {self.stake} ({self.status})"


class Jackpot(models.Model):
    """
    One jackpot tier shown in the game's jackpot bar.

    The amount is changed only through
    game.services.jackpot_service.adjust_jackpot, which checks the caller is
    an administrator and writes a JackpotAdjustment audit record. No round
    or bet logic reads or changes it.
    """

    class Icon(models.TextChoices):
        CROWN = "crown", "Crown"
        DIAMOND = "diamond", "Diamond"
        GLOBE = "globe", "Globe"
        STAR = "star", "Star"
        COINS = "coins", "Coins"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Stable identifier the game client uses (e.g. "grand").
    code = models.SlugField(max_length=30, unique=True)

    label = models.CharField(max_length=40)

    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    color = models.CharField(
        max_length=7,
        default="#2a8cff",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use a colour like #2a8cff.")],
    )

    icon = models.CharField(max_length=10, choices=Icon.choices, default=Icon.COINS)

    # Left-to-right position in the bar.
    sort_order = models.PositiveSmallIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="jackpot_amount_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.label} ({self.amount})"


class JackpotAdjustment(models.Model):
    """Audit record of every manual change to a jackpot amount."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    jackpot = models.ForeignKey(
        Jackpot,
        on_delete=models.PROTECT,
        related_name="adjustments",
    )

    previous_amount = models.DecimalField(max_digits=18, decimal_places=2)
    new_amount = models.DecimalField(max_digits=18, decimal_places=2)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="jackpot_adjustments",
    )

    reason = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.jackpot.code}: {self.previous_amount} -> {self.new_amount}"
