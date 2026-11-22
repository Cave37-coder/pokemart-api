from django.db import migrations, models


class Migration(migrations.Migration):
    """Buy-in line flag: card can't be paid for with store credit (Michael, 2026-11-22)."""

    dependencies = [("orders", "0038_cosmos_holo_type")]

    operations = [
        migrations.AddField(
            model_name="buyorderitem",
            name="no_store_credit",
            field=models.BooleanField(
                default=False,
                help_text="Mark the card 'no store credit' on the site when this invoice completes (high-value card).",
            ),
        ),
    ]
