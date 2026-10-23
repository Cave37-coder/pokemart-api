# Label only (stored code 'collected' unchanged) -- Michael, 2026-10-23: show
# "Pudo Locker" instead of "Locker/Postnet" everywhere.
from django.db import migrations, models

CHOICES = [
    ('awaiting_payment', 'Awaiting PayFast Payment'),
    ('pending', 'Order Confirmed'),
    ('pending_eft', 'Awaiting EFT Payment'),
    ('printed', 'Order Printed'),
    ('packed', 'Order Being Packed'),
    ('booked', 'Courier Booked'),
    ('ready', 'Ready for Collection'),
    ('collected', 'Deposited at Pudo Locker'),
    ('invoiced', 'Complete'),
    ('cancelled', 'Cancelled'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0027_buyorder_premium_accepted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=CHOICES, default='pending', max_length=20),
        ),
        migrations.AlterField(
            model_name='ordertracking',
            name='status',
            field=models.CharField(choices=CHOICES, max_length=20),
        ),
    ]
