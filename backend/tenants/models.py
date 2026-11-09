
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class MajorAccount(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=150)
    account_code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_major_accounts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.account_code})"


class PlayerSlot(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    major_account = models.ForeignKey(
        MajorAccount,
        on_delete=models.PROTECT,
        related_name="player_slots",
    )
    slot_number = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INACTIVE,
    )
    display_name = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["major_account", "slot_number"],
                name="unique_player_slot_per_major_account",
            ),
            models.CheckConstraint(
                condition=Q(slot_number__gte=1) & Q(slot_number__lte=8),
                name="player_slot_number_between_1_and_8",
            ),
        ]
        ordering = ["major_account", "slot_number"]

    def __str__(self):
        return (
            f"{self.major_account.name} - "
            f"Player {self.slot_number}"
        )
