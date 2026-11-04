import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accessories", "0002_sealed_barcode_price_lock_image_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="SealedCollectionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("value_when_added", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("price_paid", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("accessory", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sealed_collection_items", to="accessories.accessory")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sealed_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-added_at"]},
        ),
        migrations.AddConstraint(
            model_name="sealedcollectionitem",
            constraint=models.UniqueConstraint(fields=("user", "accessory"), name="unique_sealed_collection_item"),
        ),
    ]
