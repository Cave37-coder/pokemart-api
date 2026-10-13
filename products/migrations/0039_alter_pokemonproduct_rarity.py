from django.db import migrations, models


class Migration(migrations.Migration):
    """Choices-only change (adds pikachu_rare / futuristic_rare / rgb_rare etc.
    to RARITY_CHOICES). No database schema change; clears the 'models have
    changes not reflected in a migration' warning."""

    dependencies = [
        ('products', '0038_stockmovement_buyin_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pokemonproduct',
            name='rarity',
            field=models.CharField(
                choices=[
                    ('common', 'Common'), ('uncommon', 'Uncommon'), ('rare', 'Rare'),
                    ('holo_rare', 'Holo Rare'), ('ultra_rare', 'Ultra Rare'),
                    ('double_rare', 'Double Rare'), ('illustration_rare', 'Illustration Rare'),
                    ('special_illustration_rare', 'Special Illustration Rare'),
                    ('hyper_rare', 'Hyper Rare'), ('mega_hyper_rare', 'Mega Hyper Rare'),
                    ('mega_attack_rare', 'Mega Attack Rare'), ('secret_rare', 'Secret Rare'),
                    ('legendary', 'Legendary'), ('ace_spec', 'ACE SPEC'),
                    ('gold_star', 'Gold Star'), ('shining', 'Shining'),
                    ('pikachu_rare', 'Pikachu Rare'), ('futuristic_rare', 'Futuristic Rare'),
                    ('rgb_rare', 'RGB Rare'),
                ],
                default='common', max_length=30),
        ),
    ]
