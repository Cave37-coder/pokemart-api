from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0045_custom_collections"),
    ]

    operations = [
        migrations.AddField(
            model_name="pokemonproduct",
            name="sealed_set_name",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
    ]
