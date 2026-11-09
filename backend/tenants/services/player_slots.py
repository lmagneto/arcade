
from django.core.exceptions import ValidationError
from django.db import transaction

from tenants.models import MajorAccount, PlayerSlot
from wallets.models import Wallet


@transaction.atomic
def sync_player_slots(*, major_account_id, detected_count):
    """
    Synchronize persistent player slots with the detected mouse count.

    This service must only be called by trusted server-side code after
    verifying the major account's authorized device installation.
    """
    if (
        isinstance(detected_count, bool)
        or not isinstance(detected_count, int)
        or not 1 <= detected_count <= 8
    ):
        raise ValidationError(
            "Detected mouse count must be between 1 and 8."
        )

    major_account = MajorAccount.objects.select_for_update().get(
        pk=major_account_id
    )

    if major_account.status != MajorAccount.Status.ACTIVE:
        raise ValidationError("This major account is not active.")

    # Ensure the major account has a funding wallet.
    Wallet.objects.get_or_create(major_account=major_account)

    # Activate or create a persistent slot for each detected mouse.
    for slot_number in range(1, detected_count + 1):
        slot, created = PlayerSlot.objects.get_or_create(
            major_account=major_account,
            slot_number=slot_number,
            defaults={
                "display_name": f"Player {slot_number}",
                "status": PlayerSlot.Status.ACTIVE,
            },
        )

        # Do not override a slot suspended by an administrator.
        if not created and slot.status != PlayerSlot.Status.SUSPENDED:
            if slot.status != PlayerSlot.Status.ACTIVE:
                slot.status = PlayerSlot.Status.ACTIVE
                slot.save(update_fields=["status", "updated_at"])

        # Each persistent player slot has its own wallet.
        Wallet.objects.get_or_create(player_slot=slot)

    # Keep previously created higher-numbered slots, but deactivate them
    # when fewer mice are detected. Suspended slots remain suspended.
    PlayerSlot.objects.filter(
        major_account=major_account,
        slot_number__gt=detected_count,
        status=PlayerSlot.Status.ACTIVE,
    ).update(status=PlayerSlot.Status.INACTIVE)

    return list(
        PlayerSlot.objects.filter(
            major_account=major_account
        ).select_related("wallet").order_by("slot_number")
    )
