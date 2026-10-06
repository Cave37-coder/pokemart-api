# Labels only (stored codes unchanged) -- Michael's handwritten status list, 2026-10-06.
from django.db import migrations, models

CHOICES = [
    ('awaiting_payment', 'Awaiting PayFast Payment'),
    ('pending', 'Order Confirmed'),
    ('pending_eft', 'Awaiting EFT Payment'),
    ('printed', 'Order Printed'),
    ('packed', 'Order Being Packed'),
    ('booked', 'Courier Booked'),
    ('ready', 'Ready for Collection'),
    ('collected', 'Deposited at Locker/Postnet'),
    ('invoiced', 'Complete'),
    ('cancelled', 'Cancelled'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0020_remove_postnet_shipping_choice'),
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
