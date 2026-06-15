"""
Test ASRTG sync without ignore_conflicts to see real error
Run: python manage.py shell --command="exec(open('test_sync_asrtg2.py').read())"
"""
import requests
from decimal import Decimal
import math
from django.db import transaction
from products.models import PokemonProduct, CardSet, Era, Category

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")
rate = Decimal("16.40")

def _parse_number(raw):
    import re
    if not raw:
        return None
    raw = str(raw).split("/")[0].strip()
    try:
        return int(raw)
    except ValueError:
        match = re.match(r'^[A-Za-z]+(\d+)$', raw)
        if match:
            return int(match.group(1))
        return None

def _ext(extended_data, field_name):
    for item in extended_data:
        if item.get("name") == field_name:
            return item.get("value", "")
    return ""

r = requests.get(f"{TCGCSV_BASE}/3068/products", headers=HEADERS, timeout=30)
products = r.json().get("results", [])
r2 = requests.get(f"{TCGCSV_BASE}/3068/prices", headers=HEADERS, timeout=30)
prices = {}
for row in r2.json().get("results", []):
    pid = row.get("productId")
    sub = row.get("subTypeName", "")
    prices[(pid, sub)] = row.get("marketPrice") or row.get("lowPrice")

era = Era.objects.get(code="B7")
card_set, _ = CardSet.objects.get_or_create(
    code="ASRTG",
    defaults={"name": "Astral Radiance Trainer Gallery", "era": era}
)
category, _ = Category.objects.get_or_create(name="Pokemon")

# Try inserting just ONE record directly without bulk_create
p = products[0]
pid = p.get("productId")
ext = p.get("extendedData", [])
number_raw = _ext(ext, "Number")
card_number = _parse_number(number_raw)
usd = prices.get((pid, "Holofoil"))
zar = max(Decimal("1.50"), Decimal(str(usd)) * rate * MARKUP) if usd else Decimal("1.50")

print(f"Trying to insert: pb_id=ASRTG-{card_number}-H pid={pid} name={p['name']}")

try:
    obj = PokemonProduct(
        pb_id=f"ASRTG-{card_number}-H",
        tcgcsv_product_id=pid,
        name=p['name'],
        card_number=card_number,
        card_set=card_set,
        category=category,
        variant_override="H",
        rarity="holo_rare",
        price=zar,
        stock=0,
        is_active=True,
    )
    obj.save()
    print(f"SUCCESS: saved id={obj.id}")
    count = PokemonProduct.objects.filter(card_set__code='ASRTG').count()
    print(f"ASRTG count: {count}")
    obj.delete()
    print("Cleaned up")
except Exception as e:
    print(f"ERROR on save: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
