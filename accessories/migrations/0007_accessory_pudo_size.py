from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accessories", "0006_accessory_cart_product")]

    operations = [
        migrations.AddField(
            model_name="accessory",
            name="pudo_size",
            field=models.CharField(
                choices=[("xs", "Extra Small"), ("s", "Small"), ("m", "Medium"), ("l", "Large"), ("xl", "Extra Large")],
                default="xs", max_length=2,
                help_text="Smallest Pudo parcel this item needs. An order is never shipped in a smaller size.",
            ),
        ),
    ]
