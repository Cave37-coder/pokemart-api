from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0017_manualinvoice_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='manualinvoice',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[('eft', 'EFT'), ('cash', 'Cash'), ('card', 'Card'), ('trade', 'Trade/Credit')],
                help_text='Which method was used, if payment has been received.',
                max_length=10,
            ),
        ),
    ]
