import json
with open("tcgcsv_all_products.json") as f:
    data = json.load(f)

brs = data["2948"]["cards"]

# Show number formats
print("TCGCSV number formats:")
for c in brs[:5]:
    raw = c["_number"]
    normalized = raw.split("/")[0].lstrip("0") or "0"
    print(f"  raw={repr(raw)}  normalized={repr(normalized)}  name={c['name']}")

print()

# Now check DB
import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet
brs_set = CardSet.objects.get(code="BRS")

print("DB number formats:")
for p in PokemonProduct.objects.filter(card_set=brs_set).order_by("card_number")[:10]:
    print(f"  card_number={repr(p.card_number)}  variant={repr(p.variant_override)}  name={p.name[:40]}")

print()

# Try matching Umbreon V — card 22 in DB, what number in TCGCSV?
umbreon = [c for c in brs if "Umbreon" in c["name"]]
print("Umbreon cards in TCGCSV:")
for c in umbreon:
    print(f"  pid={c['productId']}  num={c['_number']}  subType={repr(c.get('subTypeName',''))}  name={c['name']}")

print()
db_umbreon = PokemonProduct.objects.filter(card_set=brs_set, name__icontains="Umbreon")
print("Umbreon cards in DB:")
for p in db_umbreon:
    print(f"  card_number={repr(p.card_number)}  variant={repr(p.variant_override)}  name={p.name}")
