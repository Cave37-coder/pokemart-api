# 2026-10-27: store credit -- payout on buying invoices, credit used on
# website orders and manual invoices, and the "Store Credit" payment method.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0030_buyorderitem_accessory"),
    ]

    operations = [
        migrations.AddField(
            model_name="buyorder",
            name="store_credit_amount",
            field=models.DecimalField(decimal_places=2, default=0, help_text="Part of the payout given as store credit (needs a linked site account).", max_digits=10),
        ),
        migrations.AlterField(
            model_name="buyorder",
            name="payment_method",
            field=models.CharField(blank=True, choices=[("eft", "EFT"), ("cash", "Cash"), ("card", "Card"), ("credit", "Store Credit")], help_text="Which method was used, if payment has been made.", max_length=10),
        ),
        migrations.AddField(
            model_name="order",
            name="store_credit_applied",
            field=models.DecimalField(decimal_places=2, default=0, help_text="Store credit used towards this order. Amount due = Total price - this.", max_digits=10),
        ),
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(blank=True, choices=[("payfast", "PayFast"), ("eft", "EFT / Bank Transfer"), ("coc", "Cash on Collection"), ("credit", "Store Credit")], default="payfast", max_length=20),
        ),
        migrations.AddField(
            model_name="manualinvoice",
            name="store_credit_applied",
            field=models.DecimalField(decimal_places=2, default=0, help_text="Store credit used towards this invoice (set from the invoice screen).", max_digits=10),
        ),
        migrations.AlterField(
            model_name="manualinvoice",
            name="payment_method",
            field=models.CharField(blank=True, choices=[("cash", "Cash"), ("eft", "EFT"), ("card", "Card (Payfast)"), ("trade", "Trade-In"), ("credit", "Store Credit")], help_text="Which method was used, if payment has been received.", max_length=10),
        ),
    ]
