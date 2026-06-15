import os, sys, django, json
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet
from django.db import transaction

with open("tcgcsv_all_products.json") as f:
    data = json.load(f)

with open("tcgcsv_prices.json") as f:
    prices = json.load(f)
price_by_pid = {int(k): float(v) for k, v in prices.items() if v and float(v) > 0}

import math
from decimal import Decimal
MARKUP = Decimal("1.10")
RATE = Decimal("16.49")

def to_zar(usd):
    if not usd or float(usd) <= 0:
        return None
    return Decimal(math.ceil(float(Decimal(str(usd)) * RATE * MARKUP) * 2)) / 2

def clean_name(n):
    return n.lower().replace(" (normal)","").replace(" (reverse holo)","").replace(" (holo)","").strip()

# Promo sets where numbering differs — match by name instead
PROMO_GIDS = {
    "PR-XY":  "1451",
    "PR-SV":  "22872",
    "PR-SM":  "1861",
    "PR-SW":  "2545",
    "PR-BLW": "1407",
    "PR-DPP": "1421",
    "PR":     "1418",   # WotC promos
    "SVP":    "22872",
}

total_stamped = 0
total_priced = 0

for db_code, gid_str in PROMO_GIDS.items():
    try:
        cs = CardSet.objects.get(code=db_code)
    except CardSet.DoesNotExist:
        print(f"  {db_code} not in DB, skipping")
        continue

    tcg_cards = data.get(gid_str, {}).get("cards", [])
    if not tcg_cards:
        print(f"  {db_code} no TCGCSV cards, skipping")
        continue

    # Build TCGCSV name lookup: clean_name -> (productId, raw_name)
    tcg_by_name = {}
    for c in tcg_cards:
        raw = c["name"]
        # Strip set code suffixes like "- XY01" from names
        clean = raw.split(" - ")[0].strip().lower()
        pid = int(c["productId"])
        tcg_by_name[clean] = pid

    # Get orphans for this set
    orphans = PokemonProduct.objects.filter(
        card_set=cs,
        tcgcsv_product_id__isnull=True,
        price=0
    )

    stamped = 0
    to_update = []
    for p in orphans:
        clean = clean_name(p.name)
        pid = tcg_by_name.get(clean)
        if pid:
            p.tcgcsv_product_id = pid
            usd = price_by_pid.get(pid)
            if usd:
                p.price = to_zar(usd)
                p.is_active = True
            to_update.append(p)
            stamped += 1

    if to_update:
        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, ["tcgcsv_product_id", "price", "is_active"])

    total_stamped += stamped
    total_priced += sum(1 for p in to_update if p.price and p.price > 0)
    print(f"  {db_code:15} orphans={orphans.count()}  stamped={stamped}  priced={sum(1 for p in to_update if p.price and p.price > 0)}")

print(f"\nDone. Total stamped={total_stamped}  priced={total_priced}")
