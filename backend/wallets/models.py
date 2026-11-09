
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Wallet(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    major_account = models.OneToOneField(
        "tenants.MajorAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wallet",
    )
    player_slot = models.OneToOneField(
        "tenants.PlayerSlot",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wallet",
    )
    platform_reserve = models.BooleanField(default=False)
    available_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    reserved_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        major_account__isnull=False,
                        player_slot__isnull=True,
                        platform_reserve=False,
                    )
                    | Q(
                        major_account__isnull=True,
                        player_slot__isnull=False,
                        platform_reserve=False,
                    )
                    | Q(
                        major_account__isnull=True,
                        player_slot__isnull=True,
                        platform_reserve=True,
                    )
                ),
                name="wallet_exactly_one_owner",
            ),
            models.UniqueConstraint(
                fields=["platform_reserve"],
                condition=Q(platform_reserve=True),
                name="single_platform_reserve_wallet",
            ),
            models.CheckConstraint(
                condition=Q(available_balance__gte=0),
                name="wallet_available_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(reserved_balance__gte=0),
                name="wallet_reserved_nonnegative",
            ),
        ]

    def __str__(self):
        if self.platform_reserve:
            return "Platform virtual-credit reserve"

        owner = self.major_account or self.player_slot
        return f"Wallet for {owner}"


class LedgerTransaction(models.Model):
    class TransactionType(models.TextChoices):
        ISSUANCE = "ISSUANCE", "Virtual credit issuance"
        ALLOCATION = "ALLOCATION", "Credit allocation"
        RESERVATION = "RESERVATION", "Reservation"
        RELEASE = "RELEASE", "Reservation release"
        SETTLEMENT = "SETTLEMENT", "Game settlement"
        ADJUSTMENT = "ADJUSTMENT", "Administrative adjustment"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    idempotency_key = models.CharField(
        max_length=100,
        unique=True,
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
    )
    description = models.CharField(
        max_length=255,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallet_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.reference}"


class LedgerEntry(models.Model):
    class Direction(models.TextChoices):
        DEBIT = "DEBIT", "Debit"
        CREDIT = "CREDIT", "Credit"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    direction = models.CharField(
        max_length=6,
        choices=Direction.choices,
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="ledger_entry_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.direction} {self.amount}"
