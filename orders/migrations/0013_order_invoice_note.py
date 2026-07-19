from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_alter_buyorderitem_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='invoice_note',
            field=models.TextField(
                blank=True,
                help_text='Shown to the customer on the printed/emailed invoice. For your own notes, use Internal Note instead.',
            ),
        ),
    ]
