from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0040_pokemonproduct_price_locked'),
    ]

    operations = [
        migrations.AddField(
            model_name='pokemonproduct',
            name='cost_units',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name='pokemonproduct',
            name='cost_total',
            field=models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=12),
        ),
    ]
