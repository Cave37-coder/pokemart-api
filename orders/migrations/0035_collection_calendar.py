from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0034_prep_time_estimate'),
    ]

    operations = [
        migrations.AddField(
            model_name='order', name='collection_date',
            field=models.DateField(blank=True, help_text='Collection day the customer booked at checkout.', null=True),
        ),
        migrations.AddField(
            model_name='order', name='no_rush',
            field=models.BooleanField(default=False, help_text="Customer ticked 'No Rush' -- collect whenever it suits. Left out of the prep-time figure."),
        ),
        migrations.CreateModel(
            name='CalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='e.g. Collect-a-Con, League Challenge', max_length=120)),
                ('kind', models.CharField(choices=[('event', 'Event (away)'), ('gengar', 'Gengar Games'), ('closed', 'Closed / unavailable')], default='event', max_length=10)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, help_text='Leave blank for a one-day event.', null=True)),
                ('start_time', models.TimeField(blank=True, null=True)),
                ('end_time', models.TimeField(blank=True, null=True)),
                ('venue', models.CharField(blank=True, help_text='e.g. Gengar Games, Benoni', max_length=200)),
                ('details', models.TextField(blank=True, help_text='Shown on the public calendar.')),
                ('blocks_collection', models.BooleanField(default=True, help_text='No collections from home on these days.')),
                ('public', models.BooleanField(default=True, help_text='Show on the website calendar.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['start_date', 'start_time'], 'verbose_name': 'Calendar event'},
        ),
    ]
