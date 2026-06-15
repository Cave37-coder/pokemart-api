"""
Check if the 'existing' set in sync_tcgcsv is catching ASRTG product IDs
Run: python manage.py shell --command="exec(open('check_existing_set.py').read())"
"""
import requests
from products.models import PokemonProduct

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

# Build the same 'existing' set as sync_tcgcsv does
print("Building existing set...")
existing = set(
    PokemonProduct.objects.filter(tcgcsv_product_id__isnull=False)
    .values_list("tcgcsv_product_id", "variant_override")
)
print(f"Existing set size: {len(existing)}")

# Fetch ASRTG products and prices
r = requests.get(f"{TCGCSV_BASE}/3068/products", headers=HEADERS, timeout=30)
products = r.json().get("results", [])

r2 = requests.get(f"{TCGCSV_BASE}/3068/prices", headers=HEADERS, timeout=30)
prices = {}
for row in r2.json().get("results", []):
    pid = row.get("productId")
    sub = row.get("subTypeName", "")
    prices[(pid, sub)] = row.get("marketPrice") or row.get("lowPrice")

print(f"\nASRTG products: {len(products)}, price rows: {len(prices)}")
print("\nChecking first 10 ASRTG products against existing set:")

SUBTYPE_MAP = {
    "Normal": "N", "Holofoil": "H", "Reverse Holofoil": "RH",
    "1st Edition": "N", "Unlimited": "N",
    "1st Edition Holofoil": "H", "Unlimited Holofoil": "H", "": "H",
}

skipped = created = 0
for p in products[:10]:
    pid = p.get("productId")
    name = p.get("name", "")
    ext = p.get("extendedData", [])
    number = next((i.get("value","") for i in ext if i.get("name") == "Number"), "")
    rarity = next((i.get("value","") for i in ext if i.get("name") == "Rarity"), "")

    product_prices = {sub: usd for (p_id, sub), usd in prices.items() if p_id == pid}
    if not product_prices:
        product_prices = {"": None}

    for sub, usd in product_prices.items():
        variant = SUBTYPE_MAP.get(sub, "N")
        key = (pid, variant)
        in_existing = key in existing
        print(f"  pid={pid} sub='{sub}' variant={variant} number={number} in_existing={in_existing} name={name[:25]}")
        if in_existing:
            skipped += 1
        else:
            created += 1

print(f"\nWould create: {created}, would skip: {skipped}")
