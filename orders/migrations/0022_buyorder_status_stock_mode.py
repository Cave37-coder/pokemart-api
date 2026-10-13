"""Buying invoices on the staff dashboard (2026-10-13).

Every EXISTING BuyOrder row came from the standalone POS flow: its items already
bumped pos_stock when saved and there was no status. So existing rows are
backfilled as stock_mode='pos' / status='complete' (via the temporary column
defaults below), and the defaults are then switched to the new-invoice values
('site' / 'draft')."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0021_relabel_order_statuses'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1) add with the LEGACY defaults so every existing row is backfilled as pos/complete
        migrations.AddField(
            model_name='buyorder',
            name='status',
            field=models.CharField(
                choices=[('draft', 'Draft'), ('paid', 'Paid'), ('complete', 'Complete'), ('cancelled', 'Cancelled')],
                default='complete', max_length=10),
        ),
        migrations.AddField(
            model_name='buyorder',
            name='stock_mode',
            field=models.CharField(
                choices=[('pos', 'POS (unsorted pos_stock)'), ('site', 'Live website stock on completion')],
                default='pos', max_length=4),
        ),
        # 2) new rows default to the new flow
        migrations.AlterField(
            model_name='buyorder',
            name='status',
            field=models.CharField(
                choices=[('draft', 'Draft'), ('paid', 'Paid'), ('complete', 'Complete'), ('cancelled', 'Cancelled')],
                default='draft', max_length=10),
        ),
        migrations.AlterField(
            model_name='buyorder',
            name='stock_mode',
            field=models.CharField(
                choices=[('pos', 'POS (unsorted pos_stock)'), ('site', 'Live website stock on completion')],
                default='site', max_length=4),
        ),
        migrations.AddField(
            model_name='buyorder',
            name='stock_applied',
            field=models.BooleanField(
                default=False, editable=False,
                help_text='True once completing this invoice has added its stock (guards against double-adding).'),
        ),
        migrations.AddField(
            model_name='buyorder',
            name='completed_at',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='buyorder',
            name='user',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='buy_orders_as_seller', to=settings.AUTH_USER_MODEL,
                help_text='Linked site account of the seller, if they have one.'),
        ),
    ]
