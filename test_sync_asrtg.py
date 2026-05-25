"""
Test sync of ASRTG directly with full debug output
Run: python manage.py shell --command="exec(open('test_sync_asrtg.py').read())"
"""
import requests
from decimal import Decimal, ROUND_UP
import math
from django.db import transaction
from products.models import PokemonProduct, CardSet, Era, Category

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")
rate = Decimal("16.40")

SUBTYPE_MAP = {
    "Normal": "N", "Holofoil": "H", "Reverse Holofoil": "RH",
    "1st Edition": "N", "Unlimited": "N",
    "1st Edition Holofoil": "H", "Unlimited Holofoil": "H", "": "H",
}

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

def _zar_price(usd, rate):
    raw = Decimal(str(usd)) * rate * MARKUP
    val = max(Decimal("1.50"), raw)
    return Decimal(math.ceil(float(val) * 2)) / 2

# Fetch products and prices
print("Fetching ASRTG...")
r = requests.get(f"{TCGCSV_BASE}/3068/products", headers=HEADERS, timeout=30)
products = r.json().get("results", [])
print(f"Products: {len(products)}")

r2 = requests.get(f"{TCGCSV_BASE}/3068/prices", headers=HEADERS, timeout=30)
prices = {}
for row in r2.json().get("results", []):
    pid = row.get("productId")
    sub = row.get("subTypeName", "")
    prices[(pid, sub)] = row.get("marketPrice") or row.get("lowPrice")
print(f"Prices: {len(prices)}")

era = Era.objects.get(code="B7")
card_set, _ = CardSet.objects.get_or_create(
    code="ASRTG",
    defaults={"name": "Astral Radiance Trainer Gallery", "era": era}
)
category, _ = Category.objects.get_or_create(name="Pokemon")

existing = set(
    PokemonProduct.objects.filter(tcgcsv_product_id__isnull=False)
    .values_list("tcgcsv_product_id", "variant_override")
)

to_create = []
for p in products:
    pid = p.get("productId")
    name = (p.get("name") or "").strip()
    ext = p.get("extendedData", [])
    number_raw = _ext(ext, "Number")
    rarity_raw = _ext(ext, "Rarity")
    card_number = _parse_number(number_raw)

    if card_number is None:
        print(f"  SKIP non_card: {name} number={number_raw}")
        continue

    product_prices = {sub: usd for (p_id, sub), usd in prices.items() if p_id == pid}
    if not product_prices:
        product_prices = {"": None}

    for sub, usd in product_prices.items():
        variant = SUBTYPE_MAP.get(sub, "N")
        zar = _zar_price(usd, rate) if usd else Decimal("1.50")
        pb_id = f"ASRTG-{card_number}-{variant}"

        if (pid, variant) in existing:
            print(f"  SKIP existing: {pb_id} pid={pid}")
            continue

        to_create.append(PokemonProduct(
            pb_id=pb_id,
            tcgcsv_product_id=pid,
            name=name,
            card_number=card_number,
            card_set=card_set,
            category=category,
            variant_override=variant,
            rarity="holo_rare",
            price=zar,
            stock=0,
            is_active=True,
        ))

print(f"\nTo create: {len(to_create)}")
for obj in to_create[:5]:
    print(f"  pb_id={obj.pb_id} pid={obj.tcgcsv_product_id} price={obj.price}")

if to_create:
    print("\nAttempting bulk_create...")
    try:
        with transaction.atomic():
            result = PokemonProduct.objects.bulk_create(to_create, ignore_conflicts=True)
            print(f"bulk_create returned: {len(result)} objects")
        count = PokemonProduct.objects.filter(card_set__code='ASRTG').count()
        print(f"ASRTG products in DB after: {count}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
