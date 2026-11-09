
import uuid

from django.db import models
from django.db.models import Q



class DeviceActivationRequest(models.Model):
    """
    Temporary activation request for a Windows installation.
    The major account is assigned when the request is approved.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    major_account = models.ForeignKey(
        "tenants.MajorAccount",
        on_delete=models.PROTECT,
        related_name="activation_requests",
        null=True,
        blank=True,
    )

    installation_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    code_hash = models.CharField(
        max_length=64,
        unique=True,
    )

    expires_at = models.DateTimeField()

    consumed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Activation request {self.id}"



class DeviceInstallation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    major_account = models.ForeignKey(
        "tenants.MajorAccount",
        on_delete=models.PROTECT,
        related_name="device_installations",
    )

    installation_id = models.UUIDField(unique=True)

    device_name = models.CharField(
        max_length=150,
        blank=True,
    )
    
    credential_hash = models.CharField(
    max_length=64,
    unique=True,
    null=True,
    blank=True,
)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    activated_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["major_account"],
                condition=Q(status="ACTIVE"),
                name="one_active_device_per_major_account",
            ),
        ]

    def __str__(self):
        return (
            f"{self.major_account.name} - "
            f"{self.device_name or self.installation_id}"
        )
