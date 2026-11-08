import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0047_pokemonproduct_tcg_market_zar"),
        ("accessories", "0005_sealed_on_products"),
    ]

    operations = [
        migrations.AddField(
            model_name="accessory",
            name="cart_product",
            field=models.OneToOneField(blank=True, editable=False, null=True,
                                       on_delete=django.db.models.deletion.SET_NULL,
                                       related_name="accessory_listing", to="products.pokemonproduct"),
        ),
    ]
