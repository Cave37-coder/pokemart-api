from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0025_cost_tracking'),
        ('products', '0042_pokemonproduct_sell_pct'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyorderitem',
            name='sell_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=7, null=True,
                help_text='Selling price as a % of the (condition-adjusted) TCG price. Saved on the product so the nightly sync keeps it fluid.'),
        ),
    ]
