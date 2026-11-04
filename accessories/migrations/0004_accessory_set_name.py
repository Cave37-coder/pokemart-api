from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accessories", "0003_sealedcollectionitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="accessory",
            name="set_name",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
    ]
