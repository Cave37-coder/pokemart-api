# Hand-written (sandbox can't run Django's own makemigrations here -- see
# CLAUDE.md / project convention). Mirrors ManualInvoice's existing
# discount_percent field pattern (0008_manualinvoice_discount_percent.py).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0014_remove_order_payment_confirmed_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='discount_percent',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Community discount percentage applied at checkout (snapshot), e.g. 5 for 5%.', max_digits=5),
        ),
        migrations.AddField(
            model_name='order',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Community discount amount applied at checkout (snapshot). Already subtracted from Total price.', max_digits=10),
        ),
    ]
