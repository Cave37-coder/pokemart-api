import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct

p = PokemonProduct.objects.filter(image_url="").first()
p.image_url = "https://images.pokemontcg.io/dp4/78_hires.png"
p.image_small_url = "https://images.pokemontcg.io/dp4/78.png"
p.save(update_fields=["image_url", "image_small_url"])
print(f"Fixed: {p.name} — {p.image_url}")
