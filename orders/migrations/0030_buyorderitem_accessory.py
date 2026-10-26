# 2026-10-26: buying-invoice lines can be an accessory / sealed product
# (added to Accessory.stock when the invoice is completed).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accessories", "0002_sealed_barcode_price_lock_image_source"),
        ("orders", "0029_relabel_courier_being_booked"),
    ]

    operations = [
        migrations.AddField(
            model_name="buyorderitem",
            name="accessory",
            field=models.ForeignKey(
                blank=True,
                help_text="Accessory / sealed product this line is for (instead of a card).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="buy_items",
                to="accessories.accessory",
            ),
        ),
    ]
