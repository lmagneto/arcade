from decimal import Decimal

from django.db import migrations

# Starting tiers for the jackpot bar (left to right). These are starting
# values: change them afterwards in the Django admin, which records every
# change in the adjustment log.
TIERS = [
    ("grand", "GRAND JACKPOT", "2000.45", "#d62bd6", "crown", 10),
    ("major", "MAJOR JACKPOT", "1200.00", "#2a8cff", "diamond", 20),
    ("global", "GLOBAL JACKPOT", "8167.39", "#ff8a1f", "globe", 30),
    ("mini", "MINI JACKPOT", "5430.16", "#8a4bff", "star", 40),
    ("minor", "MINOR JACKPOT", "851.67", "#2a6cff", "coins", 50),
]


def seed(apps, schema_editor):
    Jackpot = apps.get_model("game", "Jackpot")
    for code, label, amount, color, icon, order in TIERS:
        # Never touch a tier that already exists.
        Jackpot.objects.get_or_create(
            code=code,
            defaults={
                "label": label,
                "amount": Decimal(amount),
                "color": color,
                "icon": icon,
                "sort_order": order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("game", "0005_jackpots")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
