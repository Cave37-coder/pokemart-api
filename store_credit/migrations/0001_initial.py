# 2026-10-27: store credit ledger.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0030_buyorderitem_accessory"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreCreditTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, help_text="Positive = credit added, negative = credit used.", max_digits=10)),
                ("kind", models.CharField(choices=[("buyin", "Buy-in payout"), ("buyin_reversal", "Buy-in payout reversed"), ("order", "Spent on website order"), ("order_refund", "Website order credit refunded"), ("invoice", "Spent on manual invoice"), ("invoice_refund", "Manual invoice credit refunded"), ("adjustment", "Manual adjustment")], default="adjustment", max_length=20)),
                ("balance_after", models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=10)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("buy_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="store_credit_transactions", to="orders.buyorder")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("manual_invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="store_credit_transactions", to="orders.manualinvoice")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="store_credit_transactions", to="orders.order")),
                ("user", models.ForeignKey(help_text="Customer account the credit belongs to.", on_delete=django.db.models.deletion.PROTECT, related_name="store_credit_transactions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Store credit transaction",
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["user", "created_at"], name="storecredit_user_created_idx")],
            },
        ),
    ]
