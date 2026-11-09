from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from game.models import Jackpot, JackpotAdjustment


@transaction.atomic
def adjust_jackpot(
    *,
    jackpot_id,
    new_amount,
    changed_by,
    reason,
):
    if not changed_by or not changed_by.is_staff:
        raise PermissionError("Administrator access required.")

    try:
        amount = Decimal(str(new_amount))
    except Exception:
        raise ValidationError("Invalid jackpot amount.")

    if not amount.is_finite() or amount < 0:
        raise ValidationError("Amount must be zero or greater.")

    if amount.as_tuple().exponent < -2:
        raise ValidationError("Maximum two decimal places allowed.")

    if amount > Decimal("9999999999999999.99"):
        raise ValidationError("Amount exceeds the allowed maximum.")

    if not reason or not reason.strip():
        raise ValidationError("An adjustment reason is required.")

    jackpot = Jackpot.objects.select_for_update().get(
        pk=jackpot_id
    )

    previous_amount = jackpot.amount

    if previous_amount == amount:
        raise ValidationError("New amount is unchanged.")

    jackpot.amount = amount
    jackpot.save(update_fields=["amount", "updated_at"])

    JackpotAdjustment.objects.create(
        jackpot=jackpot,
        previous_amount=previous_amount,
        new_amount=amount,
        changed_by=changed_by,
        reason=reason.strip(),
    )

    return jackpot