from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0039_alter_pokemonproduct_rarity'),
    ]

    operations = [
        migrations.AddField(
            model_name='pokemonproduct',
            name='price_locked',
            field=models.BooleanField(
                default=False,
                help_text='Manual price -- the nightly TCGCSV price sync will not overwrite it.'),
        ),
    ]
