from django.db import migrations, models


class Migration(migrations.Migration):
    """Bulk buy-in / weight counter: Energies (common, holo) and Deck Exclusives (common, holo, Cosmos holo)."""

    dependencies = [("orders", "0036_weightcalibration")]

    operations = [
        migrations.AlterField(
            model_name="buyorderitem",
            name="bundle_type",
            field=models.CharField(
                blank=True, default="", max_length=20,
                choices=[("common", "Commons"), ("holo", "Holos"), ("reverse", "Reverse Holos"),
                         ("energy", "Energy - Common"), ("energy_holo", "Energy - Holo"),
                         ("deck", "Deck Exclusive - Common"), ("deck_holo", "Deck Exclusive - Holo"),
                         ("deck_cosmos", "Deck Exclusive - Cosmos Holo")],
                help_text="Set for an unsorted bulk bundle line (adds no stock until it is sorted).",
            ),
        ),
        migrations.AlterField(
            model_name="weightcalibration",
            name="card_type",
            field=models.CharField(
                max_length=20,
                choices=[("common", "Commons"), ("uncommon", "Uncommons"), ("holo", "Holos"),
                         ("reverse", "Reverse Holos"), ("energy", "Energy - Common"), ("energy_holo", "Energy - Holo"),
                         ("deck", "Deck Exclusive - Common"), ("deck_holo", "Deck Exclusive - Holo"),
                         ("deck_cosmos", "Deck Exclusive - Cosmos Holo")],
            ),
        ),
    ]
