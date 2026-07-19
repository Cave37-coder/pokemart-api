from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_buyorder_buyorderitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyorder',
            name='seller_note',
            field=models.TextField(
                blank=True,
                help_text='Shown to the seller on the printed/emailed receipt. For your own notes, use Internal Note instead.',
            ),
        ),
    ]
