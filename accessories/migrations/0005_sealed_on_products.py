import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Sealed product now lives in the product table (supertype 'Sealed') so it can be sold through the Pile.
    The Sealed Collection moves with it; Accessory.set_name is no longer needed."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("products", "0046_pokemonproduct_sealed_set_name"),
        ("accessories", "0004_accessory_set_name"),
    ]

    operations = [
        migrations.RemoveField(model_name="accessory", name="set_name"),
        migrations.DeleteModel(name="SealedCollectionItem"),
        migrations.CreateModel(
            name="SealedCollectionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("value_when_added", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("price_paid", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sealed_collection_items", to="products.pokemonproduct")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sealed_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-added_at"]},
        ),
        migrations.AddConstraint(
            model_name="sealedcollectionitem",
            constraint=models.UniqueConstraint(fields=("user", "product"), name="unique_sealed_collection_item"),
        ),
    ]
