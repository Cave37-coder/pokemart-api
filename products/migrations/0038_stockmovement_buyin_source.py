from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0037_enrichment_gap_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='source',
            field=models.CharField(
                choices=[('entry', 'Stock Entry'), ('played', 'Played copy added'), ('bundle', 'Bundle stock'),
                         ('wipe', 'Wiped to 0'), ('opening', 'Opening balance'), ('buyin', 'Buying invoice')],
                default='entry', max_length=10),
        ),
    ]
