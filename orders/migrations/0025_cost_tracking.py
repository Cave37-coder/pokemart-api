from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0024_buyorder_box_number'),
        ('products', '0041_product_cost_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyorder', name='amount_paid',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text='What was actually paid to the seller in total (blank = the invoice total). Line costs are scaled pro-rata to this.'),
        ),
        migrations.AddField(
            model_name='buyorder', name='cost_applied',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='buyorderitem', name='cost_unit_applied',
            field=models.DecimalField(blank=True, decimal_places=4, editable=False, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='buyorderitem', name='cost_units_applied',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name='buyorderitem', name='stock_product',
            field=models.ForeignKey(
                blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='products.pokemonproduct',
                help_text='The product row that actually received the stock (the played copy for non-NM lines).'),
        ),
        migrations.AddField(
            model_name='orderitem', name='unit_cost',
            field=models.DecimalField(blank=True, decimal_places=4, editable=False, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='manualinvoiceitem', name='unit_cost',
            field=models.DecimalField(blank=True, decimal_places=4, editable=False, max_digits=10, null=True),
        ),
    ]
