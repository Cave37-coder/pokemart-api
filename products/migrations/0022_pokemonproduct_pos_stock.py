from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0021_pokemonproduct_prize_pack_series'),
    ]

    operations = [
        migrations.AddField(
            model_name='pokemonproduct',
            name='pos_stock',
            field=models.PositiveIntegerField(
                default=0,
                help_text="Physical stock acquired via the POS Buy screen. Separate from live website stock -- does not affect what's purchasable on the site.",
            ),
        ),
    ]
