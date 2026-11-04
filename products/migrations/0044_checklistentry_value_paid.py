from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0043_pokemonproduct_also_in_sets"),
    ]

    operations = [
        migrations.AddField(
            model_name="checklistentry",
            name="value_when_added",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="checklistentry",
            name="price_paid",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
