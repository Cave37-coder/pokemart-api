# Bulk buy-in (Michael, 2026-10-28): a separate kind of buying invoice that registers
# bundles of Commons / Holos / Reverse Holos now, with the exact cards sorted into
# stock later. Existing invoices stay 'standard'.
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0031_store_credit_fields'),
        ('products', '0043_pokemonproduct_also_in_sets'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='buyorder',
            name='kind',
            field=models.CharField(
                max_length=10, default='standard',
                choices=[('standard', 'Standard buying invoice'), ('bulk', 'Bulk buy-in (sorted later)')],
            ),
        ),
        migrations.AddField(
            model_name='buyorderitem',
            name='bundle_type',
            field=models.CharField(
                blank=True, default='', max_length=10,
                choices=[('common', 'Commons'), ('holo', 'Holos'), ('reverse', 'Reverse Holos')],
                help_text='Set for an unsorted bulk bundle line (adds no stock until it is sorted).',
            ),
        ),
        migrations.CreateModel(
            name='BulkSortEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('condition', models.CharField(default='NM', max_length=3)),
                ('unit_cost', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='sorts', to='orders.buyorderitem')),
                ('product', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='products.pokemonproduct')),
                ('stock_product', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    help_text='The product row that received the stock (the played copy for non-NM cards).',
                    related_name='+', to='products.pokemonproduct')),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
    ]
