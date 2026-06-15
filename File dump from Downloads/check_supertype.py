import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct

# The DB has Pokémon with accent - frontend sends Pokemon without
pokemon_with_accent = PokemonProduct.objects.filter(supertype="Pokémon").count()
pokemon_without = PokemonProduct.objects.filter(supertype="Pokemon").count()
trainer = PokemonProduct.objects.filter(supertype="Trainer").count()
energy = PokemonProduct.objects.filter(supertype="Energy").count()

print(f"supertype=Pokémon (with accent): {pokemon_with_accent:,}")
print(f"supertype=Pokemon (no accent):   {pokemon_without:,}")
print(f"supertype=Trainer:               {trainer:,}")
print(f"supertype=Energy:                {energy:,}")
