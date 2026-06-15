"""
sync_meg_variants_prices.py
Syncs all MEG era sets from TCGCSV using hardcoded group IDs.
Creates missing variant records and updates prices with live USD/ZAR rate.
Run with DATABASE_URL uncommented in .env
"""
import os, django, requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet, Category
from django.utils import timezone
from collections import defaultdict
from decimal import Decimal
import math

HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
BASE = "https://tcgcsv.com/tcgplayer/3"
MARKUP = Decimal("1.10")

# MEG era group IDs from sync_tcgcsv.py
MEG_GROUPS = {
    "MEG": 24380,
    "PFL": 24448,
    "ASC": 24541,
    "POR": 24587,
    "CRI": 24655,
    # PBL not yet in GROUP_CONFIG — add when available
}

SUBTYPE_MAP = {
    "Normal":           "N",
    "Holofoil":         "H",
    "Reverse Holofoil": "RH",
    "":                 "H",
    "1st Edition":      "N",
    "Unlimited":        "N",
}

VSORT = {
    "N":0,"H":1,"RH":2,"PB":3,"MB":4,"LB":5,"FB":6,"QB":7,"UB":8,
    "DB":9,"TR":10,"SE":11,"PBP":12,"MBP":13,"CC":14,"TT":15,
}

# Fetch live USD/ZAR rate
print("Fetching live USD/ZAR rate...")
USD_ZAR = Decimal("16.30")
for url in ["https://open.er-api.com/v6/latest/USD", "https://api.exchangerate-api.com/v4/latest/USD"]:
    try:
        r = requests.get(url, timeout=10)
        rates = r.json().get("rates") or r.json().get("conversion_rates", {})
        if "ZAR" in rates:
            USD_ZAR = Decimal(str(rates["ZAR"]))
            print(f"Live rate: 1 USD = R{USD_ZAR:.4f}")
            break
    except:
        continue

def zar_price(usd):
    if not usd:
        return Decimal("1.50")
    raw = Decimal(str(usd)) * USD_ZAR * MARKUP
    val = max(Decimal("1.50"), raw)
    return Decimal(math.ceil(float(val) * 2)) / 2

try:
    cat = Category.objects.get(slug="pokemon-card")
except:
    try:
        cat = Category.objects.get(name="Pokemon")
    except:
        cat = Category.objects.first()

total_created = 0
total_updated = 0

for set_code, gid in MEG_GROUPS.items():
    try:
        db_set = CardSet.objects.get(code=set_code)
    except CardSet.DoesNotExist:
        print(f"\n{set_code}: Not in DB — skipping")
        continue

    print(f"\n{'='*50}")
    print(f"{set_code} — {db_set.name} (groupId={gid})")

    # Fetch products
    r2 = requests.get(f"{BASE}/{gid}/products", headers=HEADERS, timeout=30)
    if r2.status_code != 200:
        print(f"  Products error: {r2.status_code}")
        continue
    products_raw = r2.json().get("results", [])

    # Build product info map
    prod_map = {}
    for p in products_raw:
        pid = p["productId"]
        name = (p.get("name") or "").strip()
        number = ""
        for ed in p.get("extendedData", []):
            if ed["name"] == "Number":
                number = ed["value"]
        rarity = ""
        for ed in p.get("extendedData", []):
            if ed["name"] == "Rarity":
                rarity = ed["value"]
        prod_map[pid] = {"name": name, "number": number, "rarity": rarity}

    # Fetch prices
    r3 = requests.get(f"{BASE}/{gid}/prices", headers=HEADERS, timeout=30)
    if r3.status_code != 200:
        print(f"  Prices error: {r3.status_code}")
        continue
    prices_raw = r3.json().get("results", [])
    print(f"  Products: {len(products_raw)} | Price rows: {len(prices_raw)}")

    # Existing DB records for this set
    existing = defaultdict(dict)  # tcgcsv_product_id -> {variant_override: product}
    for p in PokemonProduct.objects.filter(card_set=db_set):
        if p.tcgcsv_product_id:
            existing[p.tcgcsv_product_id][p.variant_override] = p

    print(f"  Existing DB records: {sum(len(v) for v in existing.values())}")

    to_create = []
    to_update = []

    for price_row in prices_raw:
        pid = price_row["productId"]
        subtype = price_row.get("subTypeName") or ""
        vo = SUBTYPE_MAP.get(subtype, "N")
        market = price_row.get("marketPrice") or price_row.get("midPrice") or 0
        zar = zar_price(market)

        prod_info = prod_map.get(pid, {})
        name = prod_info.get("name", f"Product {pid}")
        number_str = prod_info.get("number", "")

        # Parse card number
        cnum = None
        if number_str:
            raw = str(number_str).split("/")[0].strip()
            try:
                cnum = int(raw)
            except:
                import re
                m = re.match(r'^[A-Za-z]+(\d+)$', raw)
                if m:
                    cnum = int(m.group(1))

        if pid in existing and vo in existing[pid]:
            # Update price
            p = existing[pid][vo]
            new_price = zar
            if market > 0 and p.price != new_price:
                p.price = new_price
                if vo == "H": p.price_holo = new_price
                elif vo == "RH": p.price_reverse_holo = new_price
                else: p.price_normal = new_price
                to_update.append(p)
        else:
            # Create missing variant
            pb_id = f"TCGCSV-{pid}-{vo}"
            if PokemonProduct.objects.filter(pb_id=pb_id).exists():
                continue
            to_create.append(PokemonProduct(
                pb_id=pb_id,
                name=name,
                description=name,
                card_number=cnum,
                variant_override=vo,
                variant_sort=VSORT.get(vo, 0),
                price=zar,
                price_holo=zar if vo == "H" else None,
                price_normal=zar if vo == "N" else None,
                price_reverse_holo=zar if vo == "RH" else None,
                tcgcsv_product_id=pid,
                card_set=db_set,
                category=cat,
                stock=0,
                is_active=True,
                created_at=timezone.now(),
                updated_at=timezone.now(),
            ))

    if to_create:
        PokemonProduct.objects.bulk_create(to_create, ignore_conflicts=True)
        print(f"  Created: {len(to_create)} missing variants")
        total_created += len(to_create)
    else:
        print(f"  Created: 0")

    if to_update:
        PokemonProduct.objects.bulk_update(
            to_update,
            ["price", "price_holo", "price_normal", "price_reverse_holo"]
        )
        print(f"  Prices updated: {len(to_update)}")
        total_updated += len(to_update)
    else:
        print(f"  Prices updated: 0")

print(f"\n{'='*50}")
print(f"DONE: Created={total_created} | Prices updated={total_updated}")
print(f"Rate: 1 USD = R{USD_ZAR:.4f} + 10% markup")
