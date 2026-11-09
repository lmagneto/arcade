from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from wallets.models import Wallet


class Command(BaseCommand):
    help = "Initialize the platform reserve wallet."

    @transaction.atomic
    def handle(self, *args, **options):
        existing = Wallet.objects.filter(platform_reserve=True)

        if existing.count() > 1:
            raise CommandError(
                "Multiple platform reserve wallets exist. "
                "Manual investigation is required."
            )

        if existing.exists():
            wallet = existing.first()

            if (
                wallet.major_account_id is not None
                or wallet.player_slot_id is not None
            ):
                raise CommandError(
                    "The existing reserve wallet has invalid ownership."
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Platform reserve already exists: {wallet.pk}"
                )
            )
            return

        try:
            wallet = Wallet.objects.create(
                platform_reserve=True,
                major_account=None,
                player_slot=None,
                available_balance="0.00",
                reserved_balance="0.00",
            )
        except IntegrityError as exc:
            raise CommandError(
                "Could not create the platform reserve wallet. "
                "Check the database constraints."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Platform reserve created successfully: {wallet.pk}"
            )
        )