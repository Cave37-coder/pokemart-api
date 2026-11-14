from django.db import migrations, models

_TYPES = [("common", "Commons"), ("holo", "Holos"), ("reverse", "Reverse Holos"), ("cosmos", "Cosmos Holo"),
          ("energy", "Energy - Common"), ("energy_holo", "Energy - Holo"),
          ("deck", "Deck Exclusive - Common"), ("deck_holo", "Deck Exclusive - Holo"),
          ("deck_cosmos", "Deck Exclusive - Cosmos Holo")]


class Migration(migrations.Migration):
    """Cosmos Holo as its own bulk buy-in / weight counter type (per set or era)."""

    dependencies = [("orders", "0037_bulk_energy_deck_types")]

    operations = [
        migrations.AlterField(
            model_name="buyorderitem", name="bundle_type",
            field=models.CharField(blank=True, default="", max_length=20, choices=_TYPES,
                                   help_text="Set for an unsorted bulk bundle line (adds no stock until it is sorted)."),
        ),
        migrations.AlterField(
            model_name="weightcalibration", name="card_type",
            field=models.CharField(max_length=20, choices=_TYPES + [("uncommon", "Uncommons")]),
        ),
    ]
