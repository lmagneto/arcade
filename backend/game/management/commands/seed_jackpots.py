from decimal import Decimal

from django.core.management.base import BaseCommand

from game.models import Jackpot


INITIAL_JACKPOTS = [
    {
        "code": "grand",
        "label": "GRAND JACKPOT",
        "amount": Decimal("2000.45"),
        "color": "#d62bd6",
        "icon": "crown",
        "display_order": 1,
    },
    {
        "code": "major",
        "label": "MAJOR JACKPOT",
        "amount": Decimal("1200.00"),
        "color": "#2a8cff",
        "icon": "diamond",
        "display_order": 2,
    },
    {
        "code": "global",
        "label": "GLOBAL JACKPOT",
        "amount": Decimal("8167.39"),
        "color": "#ff8a1f",
        "icon": "globe",
        "display_order": 3,
    },
    {
        "code": "mini",
        "label": "MINI JACKPOT",
        "amount": Decimal("5430.16"),
        "color": "#8a4bff",
        "icon": "star",
        "display_order": 4,
    },
    {
        "code": "minor",
        "label": "MINOR JACKPOT",
        "amount": Decimal("851.67"),
        "color": "#2a6cff",
        "icon": "coins",
        "display_order": 5,
    },
]


class Command(BaseCommand):
    help = "Create initial Arcade Bets jackpots."

    def handle(self, *args, **options):
        for data in INITIAL_JACKPOTS:
            jackpot, created = Jackpot.objects.get_or_create(
                code=data["code"],
                defaults=data,
            )

            status = "Created" if created else "Already exists"

            self.stdout.write(
                f"{status}: {jackpot.label} - {jackpot.amount}"
            )