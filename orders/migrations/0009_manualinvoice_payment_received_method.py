from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_manualinvoice_discount_percent'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='manualinvoice',
            name='eft_confirmed',
        ),
        migrations.AddField(
            model_name='manualinvoice',
            name='payment_received',
            field=models.BooleanField(
                default=False,
                help_text="Tick once you've personally verified payment came in.",
            ),
        ),
        migrations.AddField(
            model_name='manualinvoice',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[('eft', 'EFT'), ('cash', 'Cash'), ('card', 'Card')],
                help_text='Which method was used, if payment has been received.',
                max_length=10,
            ),
        ),
    ]
