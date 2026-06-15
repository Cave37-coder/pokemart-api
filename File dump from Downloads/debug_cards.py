import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import PokemonProduct

VORDER = {"N": 0, "RH": 1, "H": 2}
cards = list(PokemonProduct.objects
    .filter(card_set__code="POR", is_active=True)
    .order_by("card_number")
    .values("id", "name", "card_number", "variant_override", "stock"))

cards = sorted(cards, key=lambda c: (c["card_number"], VORDER.get(c["variant_override"] or "N", 9)))

print(f"Total cards: {len(cards)}")
print("First 5:")
for c in cards[:5]:
    print(f"  #{c['card_number']:03} {c['variant_override']:5} {c['name']}")
