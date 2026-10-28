from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0032_bulk_buyin'),
    ]

    operations = [
        migrations.AddField(model_name='order', name='pudo_locker_code', field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='order', name='pudo_shipment_id', field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='order', name='pudo_pin', field=models.CharField(blank=True, help_text='Drop-off PIN returned by Pudo for the sender.', max_length=20)),
        migrations.AddField(model_name='order', name='pudo_booked_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='order', name='pudo_booking_error', field=models.CharField(blank=True, max_length=300)),
    ]
