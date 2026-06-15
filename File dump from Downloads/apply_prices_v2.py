import os, sys, django, json, math
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db import transaction
from decimal import Decimal

MARKUP = Decimal("1.10")
RATE = Decimal("16.49")

def to_zar(usd):
    return Decimal(math.ceil(float(Decimal(str(usd)) * RATE * MARKUP) * 2)) / 2

SUBTYPE_TO_VARIANT = {
    "Normal": "N",
    "Holofoil": "H",
    "Reverse Holofoil": "RH",
    "1st Edition Normal": "N",
    "1st Edition Holofoil": "H",
    "Unlimited Normal": "N",
    "Unlimited Holofoil": "H",
    "": "H",
}

print("Loading tcgcsv_prices_full.json...")
with open("tcgcsv_prices_full.json") as f:
    prices = json.load(f)
print(f"  {len(prices):,} price rows loaded")

# Build lookup: (tcgcsv_product_id, variant) -> price
price_map = {}
for key, usd in prices.items():
    pid_str, subtype = key.split("|", 1)
    pid = int(pid_str)
    variant = SUBTYPE_TO_VARIANT.get(subtype, "N")
    price_map[(pid, variant)] = float(usd)

print(f"  {len(price_map):,} (productId, variant) pairs")

# Update DB records
print("Updating prices by (tcgcsv_product_id, variant)...")
updated = skipped = no_price = 0
to_update = []

for p in PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True).iterator(chunk_size=2000):
    pid = p.tcgcsv_product_id
    var = p.variant_override or "N"
    
    # Normalize variant to TCGCSV subtype equivalent
    if var in ("N", "1E"):
        lookup_var = "N"
    elif var in ("H", "SHN"):
        lookup_var = "H"
    elif var == "RH":
        lookup_var = "RH"
    else:
        lookup_var = "N"  # V, VX, UR etc — use Normal price
    
    usd = price_map.get((pid, lookup_var))
    if usd is None:
        # fallback: any price for this productId
        for v in ["N", "H", "RH"]:
            usd = price_map.get((pid, v))
            if usd:
                break
    
    if usd is None:
        no_price += 1
        continue
    
    new_price = to_zar(usd)
    if p.price == new_price:
        skipped += 1
        continue
    
    p.price = new_price
    to_update.append(p)
    updated += 1
    
    if len(to_update) >= 2000:
        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, ["price"])
        print(f"  ...wrote {updated:,}")
        to_update = []

if to_update:
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(to_update, ["price"])

print(f"\nDone. Updated={updated:,}  Skipped={skipped:,}  No price={no_price:,}")
