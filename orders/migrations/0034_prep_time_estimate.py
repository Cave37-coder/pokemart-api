from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0033_pudo_booking'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrepTimeEstimate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('low_days', models.PositiveSmallIntegerField(default=2)),
                ('high_days', models.PositiveSmallIntegerField(default=4)),
                ('median_days', models.FloatField(blank=True, null=True)),
                ('p80_days', models.FloatField(blank=True, null=True)),
                ('sample_size', models.PositiveIntegerField(default=0)),
                ('open_orders', models.PositiveIntegerField(default=0)),
                ('oldest_open_days', models.FloatField(default=0)),
                ('source', models.CharField(default='default', editable=False, max_length=20)),
                ('computed_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('override_low_days', models.PositiveSmallIntegerField(blank=True, help_text='Set both override days to replace the calculated range (e.g. event weekend).', null=True)),
                ('override_high_days', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('override_message', models.CharField(blank=True, help_text="Optional note shown with the time, e.g. 'At Collect-a-Con this weekend - orders resume Monday.'", max_length=200)),
                ('override_until', models.DateField(blank=True, help_text='Override (days and message) switches itself off after this date. Leave blank to keep it on.', null=True)),
            ],
            options={
                'verbose_name': 'Order preparation time',
                'verbose_name_plural': 'Order preparation time',
            },
        ),
    ]
