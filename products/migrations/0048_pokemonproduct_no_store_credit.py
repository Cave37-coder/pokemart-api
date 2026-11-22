from django.db import migrations, models


class Migration(migrations.Migration):
    """Cards that store credit can't pay for (Michael, 2026-11-22)."""

    dependencies = [
        ("products", "0047_pokemonproduct_tcg_market_zar"),
    ]

    operations = [
        migrations.AddField(
            model_name="pokemonproduct",
            name="no_store_credit",
            field=models.BooleanField(
                default=False,
                help_text="Cannot be paid for with store credit (high-value cards). Customers see a 'No store credit' badge.",
            ),
        ),
    ]
