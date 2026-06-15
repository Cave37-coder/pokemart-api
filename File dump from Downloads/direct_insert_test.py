"""
Try inserting ASRTG cards using individual saves instead of bulk_create
Run: python manage.py shell --command="exec(open('direct_insert_test.py').read())"
"""
import requests
from decimal import Decimal
import math
from products.models import PokemonProduct, CardSet, Era, Category

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
rate = Decimal("16.40")
MARKUP = Decimal("1.10")

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

def _ext(ext, field):
    for item in ext:
        if item.get("name") == field:
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
card_set = CardSet.objects.get(code="ASRTG")
category, _ = Category.objects.get_or_create(name="Pokemon")

created = 0
errors = 0
for p in products[:5]:  # Test first 5 only
    pid = p.get("productId")
    name = (p.get("name") or "").strip()
    ext = p.get("extendedData", [])
    number_raw = _ext(ext, "Number")
    card_number = _parse_number(number_raw)
    usd = prices.get((pid, "Holofoil"))
    zar = max(Decimal("1.50"), Decimal(str(usd)) * rate * MARKUP) if usd else Decimal("1.50")
    pb_id = f"ASRTG-{card_number}-H"

    # Skip if exists
    if PokemonProduct.objects.filter(pb_id=pb_id).exists():
        print(f"  SKIP: {pb_id} already exists")
        continue

    try:
        obj = PokemonProduct.objects.create(
            pb_id=pb_id,
            tcgcsv_product_id=pid,
            name=name,
            card_number=card_number,
            card_set=card_set,
            category=category,
            variant_override="H",
            rarity="holo_rare",
            price=zar,
            stock=0,
            is_active=True,
        )
        print(f"  CREATED: {pb_id} id={obj.id}")
        created += 1
    except Exception as e:
        print(f"  ERROR {pb_id}: {e}")
        errors += 1

print(f"\nCreated: {created} Errors: {errors}")
print(f"ASRTG DB count: {PokemonProduct.objects.filter(card_set__code='ASRTG').count()}")
