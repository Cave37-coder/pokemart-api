from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0041_product_cost_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='pokemonproduct',
            name='sell_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=7, null=True,
                help_text='Sell at this % of the (condition-adjusted) TCG-derived price; updated by the nightly sync.'),
        ),
    ]
