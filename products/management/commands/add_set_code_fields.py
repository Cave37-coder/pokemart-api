# Migration: add tcgio_code and bulba_code to CardSet
# Save to: C:\Users\texca\pokemart-api\products\migrations\add_set_code_fields.py
# Run: python manage.py migrate products

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Update this to match your latest migration
        ('products', '0004_cardset_logo_url_cardset_release_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cardset',
            name='tcgio_code',
            field=models.CharField(
                max_length=20, blank=True, default='',
                help_text='pokemontcg.io API set code (e.g. swsh1). Used for API lookups only.'
            ),
        ),
        migrations.AddField(
            model_name='cardset',
            name='bulba_code',
            field=models.CharField(
                max_length=20, blank=True, default='',
                help_text='Official Bulbapedia set abbreviation (e.g. SSH)'
            ),
        ),
    ]
