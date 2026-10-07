from django.db import migrations, models


def _char(n):
    return models.CharField(blank=True, max_length=n)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0036_stockmovement'),
    ]

    operations = [
        migrations.AddField(model_name='pokemonproduct', name='attack_1_cost', field=_char(80)),
        migrations.AddField(model_name='pokemonproduct', name='attack_2_cost', field=_char(80)),
        migrations.AddField(model_name='pokemonproduct', name='attack_3_name', field=_char(200)),
        migrations.AddField(model_name='pokemonproduct', name='attack_3_damage', field=_char(20)),
        migrations.AddField(model_name='pokemonproduct', name='attack_3_text', field=models.TextField(blank=True)),
        migrations.AddField(model_name='pokemonproduct', name='attack_3_cost', field=_char(80)),
        migrations.AddField(model_name='pokemonproduct', name='ability_2_name', field=_char(200)),
        migrations.AddField(model_name='pokemonproduct', name='ability_2_type', field=_char(50)),
        migrations.AddField(model_name='pokemonproduct', name='ability_2_text', field=models.TextField(blank=True)),
        migrations.AddField(model_name='pokemonproduct', name='stage',
                            field=models.CharField(blank=True, help_text='Basic / Stage 1 / Stage 2 / Mega etc.', max_length=40)),
        migrations.AddField(model_name='pokemonproduct', name='evolves_from', field=_char(100)),
        migrations.AddField(model_name='pokemonproduct', name='evolves_to',
                            field=models.CharField(blank=True, help_text='Comma-separated.', max_length=200)),
        migrations.AddField(model_name='pokemonproduct', name='rules_text',
                            field=models.TextField(blank=True, help_text='Rule box text (ex / V / Mega rules).')),
        migrations.AddField(model_name='pokemonproduct', name='ancient_trait', field=_char(400)),
        migrations.AddField(model_name='pokemonproduct', name='card_level', field=_char(10)),
    ]
