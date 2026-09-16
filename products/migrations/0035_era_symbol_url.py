from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0034_rename_bundleopportunity_set_tier_idx_products_bu_card_se_c411bc_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='era',
            name='symbol_url',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
