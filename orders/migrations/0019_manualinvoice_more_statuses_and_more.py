# Hand-written (sandbox can't run Django's own makemigrations here -- see
# CLAUDE.md / project convention). Covers the 2026-09-04 "structure manual
# invoicing the same as normal order" change: Order.status relabels Packed
# -> Preparing; ManualInvoice.status gains Awaiting EFT Payment / Order
# Printed / Ready for Collection (and its own Packed -> Preparing relabel);
# ManualInvoice.payment_method reordered + relabelled to Cash / EFT / Card
# (Payfast) / Trade-In. No DB columns change size or type -- choices-only.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0018_alter_manualinvoice_payment_method'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('awaiting_payment', 'Awaiting Payment'),
                    ('pending', 'Order Received'),
                    ('pending_eft', 'Awaiting EFT Payment'),
                    ('printed', 'Order Printed'),
                    ('packed', 'Order Preparing'),
                    ('booked', 'Courier Booking'),
                    ('ready', 'Ready for Collection'),
                    ('collected', 'Courier Collected'),
                    ('invoiced', 'Complete'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='manualinvoice',
            name='status',
            field=models.CharField(
                choices=[
                    ('created', 'Created'),
                    ('pending_eft', 'Awaiting EFT Payment'),
                    ('printed', 'Order Printed'),
                    ('packed', 'Preparing'),
                    ('ready', 'Ready for Collection'),
                    ('payment_confirmed', 'Payment Confirmed'),
                    ('complete', 'Complete'),
                    ('cancelled', 'Cancelled'),
                ],
                default='created',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='manualinvoice',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('cash', 'Cash'),
                    ('eft', 'EFT'),
                    ('card', 'Card (Payfast)'),
                    ('trade', 'Trade-In'),
                ],
                help_text='Which method was used, if payment has been received.',
                max_length=10,
            ),
        ),
    ]
