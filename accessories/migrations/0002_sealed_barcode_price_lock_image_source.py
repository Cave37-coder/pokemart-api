# 2026-10-26: buying-invoice support for accessories & sealed product.
# Adds the "sealed" category, an optional manufacturer barcode (future POS),
# a price lock (so sync_accessories keeps buy-in/admin prices) and the
# original image source URL (image_url itself is always re-hosted on R2).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accessories", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accessory",
            name="category",
            field=models.CharField(
                choices=[
                    ("sleeves", "Card Sleeves"),
                    ("deck_boxes", "Deck Boxes"),
                    ("storage_tins", "Card Storage Tins"),
                    ("life_counters", "Life Counters"),
                    ("playmats", "Playmats"),
                    ("protective_pages", "Protective Pages"),
                    ("storage_albums", "Storage Albums"),
                    ("collectible_storage", "Collectible Storage"),
                    ("supply_bundles", "Supply Bundles"),
                    ("supplies", "Supplies"),
                    ("sealed", "Sealed Product"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="accessory",
            name="image_source_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="accessory",
            name="barcode",
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="accessory",
            name="price_locked",
            field=models.BooleanField(default=False, help_text="Keep this price -- the TCGCSV sync will not overwrite it."),
        ),
    ]
