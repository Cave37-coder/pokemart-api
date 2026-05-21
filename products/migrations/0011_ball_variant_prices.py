from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("products", "0010_pokemonproduct_tcgcsv_product_id"),
    ]
    operations = [
        migrations.AddField(model_name="pokemonproduct", name="price_pokeball", field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="pokemonproduct", name="price_masterball", field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="pokemonproduct", name="price_friendball", field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="pokemonproduct", name="price_loveball", field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="pokemonproduct", name="price_quickball", field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="pokemonproduct", name="price_duskball", field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="pokemonproduct", name="price_rh_holo", field=models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
    ]
