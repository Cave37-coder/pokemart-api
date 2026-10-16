from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0042_pokemonproduct_sell_pct'),
    ]

    operations = [
        migrations.AddField(
            model_name='pokemonproduct',
            name='also_in_sets',
            field=models.ManyToManyField(
                blank=True, related_name='shared_products', to='products.cardset',
                help_text='Other sets whose checklist also includes this card (shared Energy).'),
        ),
    ]
