"""
Check if tcgcsv_product_id conflicts are causing silent failures
Run: python manage.py shell --command="exec(open('check_pid_conflict.py').read())"
"""
import requests
from products.models import PokemonProduct

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

# Fetch first few products from ASRTG and check if their pids exist in DB
r = requests.get(f"{TCGCSV_BASE}/3068/products", headers=HEADERS, timeout=30)
products = r.json().get("results", [])[:10]

print("ASRTG first 10 productIds vs DB:")
for p in products:
    pid = p.get("productId")
    name = p.get("name", "")
    exists = PokemonProduct.objects.filter(tcgcsv_product_id=pid).values('pb_id', 'card_set__code').first()
    if exists:
        print(f"  pid={pid} CONFLICT -> pb_id={exists['pb_id']} set={exists['card_set__code']} | {name[:30]}")
    else:
        print(f"  pid={pid} OK | {name[:30]}")

# Also check TOT22
r2 = requests.get(f"{TCGCSV_BASE}/3179/products", headers=HEADERS, timeout=30)
products2 = r2.json().get("results", [])[:5]
print(f"\nTOT22 first 5 productIds vs DB:")
for p in products2:
    pid = p.get("productId")
    name = p.get("name", "")
    exists = PokemonProduct.objects.filter(tcgcsv_product_id=pid).values('pb_id', 'card_set__code').first()
    if exists:
        print(f"  pid={pid} CONFLICT -> pb_id={exists['pb_id']} set={exists['card_set__code']} | {name[:30]}")
    else:
        print(f"  pid={pid} OK | {name[:30]}")
