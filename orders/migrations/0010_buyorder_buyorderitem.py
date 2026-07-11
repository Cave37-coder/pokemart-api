from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_manualinvoice_payment_received_method'),
        ('products', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BuyOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('buy_number', models.CharField(blank=True, editable=False, max_length=20, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seller_name', models.CharField(max_length=255)),
                ('seller_email', models.EmailField(blank=True, max_length=254)),
                ('seller_phone', models.CharField(blank=True, max_length=50)),
                ('internal_note', models.TextField(blank=True, help_text='Your own notes only -- not shown to the seller.')),
                ('payment_made', models.BooleanField(default=False, help_text="Tick once you've personally paid the seller.")),
                ('payment_method', models.CharField(blank=True, choices=[('eft', 'EFT'), ('cash', 'Cash'), ('card', 'Card')], help_text='Which method was used, if payment has been made.', max_length=10)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='buy_orders', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='BuyOrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(blank=True, max_length=500)),
                ('set_name', models.CharField(blank=True, max_length=255)),
                ('card_number', models.CharField(blank=True, max_length=20)),
                ('variant', models.CharField(blank=True, max_length=10)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('unit_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='What you actually paid per card/item.', max_digits=10)),
                ('buy_order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='orders.buyorder')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.pokemonproduct')),
            ],
            options={'ordering': ['id']},
        ),
    ]
