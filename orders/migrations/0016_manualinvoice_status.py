# Hand-written (sandbox can't run Django's own makemigrations here -- see
# CLAUDE.md / project convention).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0015_order_discount_percent_order_discount_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='manualinvoice',
            name='status',
            field=models.CharField(
                choices=[
                    ('created', 'Created'),
                    ('payment_confirmed', 'Payment Confirmed'),
                    ('packed', 'Packed'),
                    ('complete', 'Complete'),
                    ('cancelled', 'Cancelled'),
                ],
                default='created',
                max_length=20,
            ),
        ),
    ]
