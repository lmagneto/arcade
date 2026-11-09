import string
import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from devices.models import DeviceActivationRequest, DeviceInstallation
from tenants.models import MajorAccount


ACTIVATION_CODE_LIFETIME_MINUTES = 10
PAIRING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_pairing_code(length=8):
    return "".join(
        secrets.choice(PAIRING_CODE_ALPHABET)
        for _ in range(length)
    )

def _hash_code(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@transaction.atomic
def create_pc_pairing_request(*, installation_id):
    try:
        installation_uuid = UUID(str(installation_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid installation ID.")

    existing = (
        DeviceActivationRequest.objects
        .select_for_update()
        .filter(installation_id=installation_uuid)
        .first()
    )

    if existing is not None:
        if existing.consumed_at is not None:
            raise ValidationError(
                "This installation has already been activated."
            )

        if existing.major_account_id is not None:
            raise ValidationError(
                "This installation has already been approved. "
                "Complete activation instead of requesting another code."
            )

    for _ in range(5):
        raw_code = generate_pairing_code()
        code_hash = _hash_code(raw_code)

        if DeviceActivationRequest.objects.filter(
            code_hash=code_hash
        ).exists():
            continue

        expires_at = timezone.now() + timedelta(
            minutes=ACTIVATION_CODE_LIFETIME_MINUTES
        )

        if existing is not None:
            existing.code_hash = code_hash
            existing.expires_at = expires_at
            existing.save(update_fields=["code_hash", "expires_at"])
            request = existing
        else:
            request = DeviceActivationRequest.objects.create(
                major_account=None,
                installation_id=installation_uuid,
                code_hash=code_hash,
                expires_at=expires_at,
            )

        return {
            "installation_id": str(request.installation_id),
            "pairing_code": raw_code,
            "expires_at": request.expires_at.isoformat(),
        }

    raise ValidationError(
        "Could not generate a unique pairing code. Please retry."
    )

@transaction.atomic
def create_activation_request(*, major_account_id):
    major_account = MajorAccount.objects.select_for_update().get(
        pk=major_account_id
    )

    if major_account.status != MajorAccount.Status.ACTIVE:
        raise ValidationError("This major account is not active.")

    if DeviceInstallation.objects.filter(
        major_account=major_account,
        status=DeviceInstallation.Status.ACTIVE,
    ).exists():
        raise ValidationError(
            "This major account already has an active installation. "
            "Revoke it before activating another installation."
        )

    raw_code = secrets.token_urlsafe(32)

    request = DeviceActivationRequest.objects.create(
        major_account=major_account,
        code_hash=_hash_code(raw_code),
        expires_at=timezone.now() + timedelta(
            minutes=ACTIVATION_CODE_LIFETIME_MINUTES
        ),
    )

    return {
        "activation_request_id": str(request.id),
        "installation_id": str(request.installation_id),
        "activation_code": raw_code,
        "expires_at": request.expires_at.isoformat(),
    }


@transaction.atomic
def activate_installation(
    *,
    installation_id,
    activation_code,
    device_name="",
):
    try:
        installation_uuid = UUID(str(installation_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid installation ID.")

    if not isinstance(activation_code, str) or not activation_code:
        raise ValidationError("An activation code is required.")

    code_hash = _hash_code(activation_code)

    try:
        activation_request = (
            DeviceActivationRequest.objects.select_for_update()
            .get(code_hash=code_hash)
        )
    except DeviceActivationRequest.DoesNotExist:
        raise ValidationError("Invalid activation code.")

    if activation_request.consumed_at is not None:
        raise ValidationError("This activation code has already been used.")

    if activation_request.expires_at <= timezone.now():
        raise ValidationError("This activation code has expired.")

    if activation_request.installation_id != installation_uuid:
        raise ValidationError(
            "The installation ID does not match this activation code."
        )

    major_account = MajorAccount.objects.select_for_update().get(
        pk=activation_request.major_account_id
    )

    if major_account.status != MajorAccount.Status.ACTIVE:
        raise ValidationError("This major account is not active.")

    if DeviceInstallation.objects.filter(
        major_account=major_account,
        status=DeviceInstallation.Status.ACTIVE,
    ).exists():
        raise ValidationError(
            "This major account already has an active installation."
        )

    device_name = (device_name or "").strip()[:150]
    device_credential = secrets.token_urlsafe(48)

    installation = DeviceInstallation.objects.create(
        major_account=major_account,
        installation_id=activation_request.installation_id,
        device_name=device_name,
        credential_hash=_hash_code(device_credential),
        status=DeviceInstallation.Status.ACTIVE,
    )

    activation_request.consumed_at = timezone.now()
    activation_request.save(update_fields=["consumed_at"])

    return {
        "installation": installation,
        "device_credential": device_credential,
    }
