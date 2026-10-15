from django.db import migrations, models


def backfill_boxes(apps, schema_editor):
    """Give existing site-built buying invoices a box number, oldest first."""
    BuyOrder = apps.get_model('orders', 'BuyOrder')
    n = 0
    for bo in BuyOrder.objects.filter(stock_mode='site', box_number__isnull=True).order_by('id'):
        n += 1
        bo.box_number = n
        bo.save(update_fields=['box_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0023_buyorderitem_condition_sell_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyorder',
            name='box_number',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Storage box the stock from this invoice is put in. Auto-assigned; can be changed.'),
        ),
        migrations.RunPython(backfill_boxes, migrations.RunPython.noop),
    ]
