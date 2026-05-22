import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import PokemonProduct
from django.db.models import Count

print("SVI variant distribution:")
for row in PokemonProduct.objects.filter(card_set__code="SVI").values("variant_override").annotate(c=Count("id")).order_by("-c"):
    print(f"  {row['variant_override']:10} {row['c']:,}")

print()
print("SVI card 15:")
for p in PokemonProduct.objects.filter(card_set__code="SVI", card_number=15):
    print(f"  name={p.name} variant={p.variant_override} stock={p.stock}")
