from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0046_pokemonproduct_sealed_set_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="pokemonproduct",
            name="tcg_market_zar",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
    ]
