from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0027_pokedexcollectionentry_caught_for_pokedex_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='era',
            name='logo_url',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
