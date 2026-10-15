from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0022_buyorder_status_stock_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyorderitem',
            name='condition',
            field=models.CharField(
                choices=[('NM', 'Near Mint'), ('LP', 'Lightly Played'), ('MP', 'Moderately Played'),
                         ('HP', 'Heavily Played'), ('DMG', 'Damaged')],
                default='NM', max_length=3,
                help_text='Condition of the cards bought. Non-NM stock goes to the played copy of the card.'),
        ),
        migrations.AddField(
            model_name='buyorderitem',
            name='sell_price',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text='Optional: price to sell at on the site. Set (and locked) when the invoice is completed.'),
        ),
        migrations.AddField(
            model_name='buyorderitem',
            name='tcg_price',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text='Site/TCG price of the card when this line was saved (snapshot, for the buy-in rate shown on the client receipt).'),
        ),
    ]
