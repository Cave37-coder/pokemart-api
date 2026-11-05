import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0035_collection_calendar"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeightCalibration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(choices=[("era", "Era"), ("set", "Specific set")], max_length=3)),
                ("scope_key", models.CharField(help_text="Era code (SV, SWSH...) or set code", max_length=20)),
                ("card_type", models.CharField(choices=[("common", "Commons"), ("uncommon", "Uncommons"), ("holo", "Holos"), ("reverse", "Reverse Holos"), ("energy", "Basic Energy")], max_length=10)),
                ("grams_per_card", models.DecimalField(decimal_places=4, max_digits=7)),
                ("sample_cards", models.PositiveIntegerField(default=0, help_text="Hand-counted cards behind this average")),
                ("sample_grams", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["scope", "scope_key", "card_type"]},
        ),
        migrations.AddConstraint(
            model_name="weightcalibration",
            constraint=models.UniqueConstraint(fields=("scope", "scope_key", "card_type"), name="unique_weight_calibration"),
        ),
    ]
