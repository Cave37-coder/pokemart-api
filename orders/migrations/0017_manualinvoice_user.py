from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0016_manualinvoice_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='manualinvoice',
            name='user',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Link to this customer's site account, if they have one and you know it. Leave blank for a walk-in with no account.",
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='manual_invoices_as_customer',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
