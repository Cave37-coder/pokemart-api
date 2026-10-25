# Label only (stored code 'booked' unchanged) -- Michael, 2026-10-25:
# "Courier Booked" -> "Courier Being Booked".
from django.db import migrations, models

CHOICES = [
    ('awaiting_payment', 'Awaiting PayFast Payment'),
    ('pending', 'Order Confirmed'),
    ('pending_eft', 'Awaiting EFT Payment'),
    ('printed', 'Order Printed'),
    ('packed', 'Order Being Packed'),
    ('booked', 'Courier Being Booked'),
    ('ready', 'Ready for Collection'),
    ('collected', 'Deposited at Pudo Locker'),
    ('invoiced', 'Complete'),
    ('cancelled', 'Cancelled'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0028_relabel_collected_pudo_locker'),
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
