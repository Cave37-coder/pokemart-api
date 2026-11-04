import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("products", "0044_checklistentry_value_paid"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomCollection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="custom_collections", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CustomCollectionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("value_when_added", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("price_paid", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("collection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="products.customcollection")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="custom_collection_items", to="products.pokemonproduct")),
            ],
            options={"ordering": ["-added_at"]},
        ),
        migrations.AddConstraint(
            model_name="customcollectionitem",
            constraint=models.UniqueConstraint(fields=("collection", "product"), name="unique_custom_collection_item"),
        ),
    ]
