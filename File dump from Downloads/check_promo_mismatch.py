import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet
import json

# Check PR-XY orphans vs TCGCSV
cs = CardSet.objects.get(code="PR-XY")
orphans = PokemonProduct.objects.filter(card_set=cs, tcgcsv_product_id__isnull=True, price=0)
print(f"PR-XY orphans in DB: {orphans.count()}")
print("Sample orphan card_numbers:")
for p in orphans[:10]:
    print(f"  card_number={p.card_number}  variant={p.variant_override}  name={p.name[:40]}")

print()

# Check what TCGCSV has for PR-XY (gid 1451)
with open("tcgcsv_all_products.json") as f:
    data = json.load(f)
tcg_cards = data["1451"]["cards"]
print(f"PR-XY cards in TCGCSV: {len(tcg_cards)}")
print("Sample TCGCSV numbers:")
for c in tcg_cards[:10]:
    print(f"  number={c['_number']}  name={c['name']}")
