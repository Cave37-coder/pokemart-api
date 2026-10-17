from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0026_buyorderitem_sell_pct'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyorder',
            name='premium_accepted',
            field=models.BooleanField(
                default=False,
                help_text='Paid above the invoice on purpose (e.g. to secure stock). Only changes how the Cost panel reports it.'),
        ),
    ]
