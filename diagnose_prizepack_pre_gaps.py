"""
diagnose_prizepack_pre_gaps.py
Read-only, focused version of diagnose_no_match_products.py -- only checks
Prize Pack Series Cards (group 22880) and SV: Prismatic Evolutions (group
23821), the two groups flagged as worth a closer look. Lists EVERY
unmatched product in full (not a sample), since the counts are small
enough (167 + 51) to review completely.

Usage:
    python manage.py shell -c "exec(open('diagnose_prizepack_pre_gaps.py').read())"
"""

import requests
import time
from products.models import PokemonProduct

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

TARGET_GROUPS = {
    22880: "Prize Pack Series Cards (PRIZEPACK)",
    23821: "SV: Prismatic Evolutions (PRE)",
}

print("Building existing product_id set from DB...")
existing_pids = set(
    PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True)
    .values_list('tcgcsv_product_id', flat=True)
)
print(f"  {len(existing_pids):,} distinct product_ids already in DB")
print()

for gid, label in TARGET_GROUPS.items():
    print("=" * 70)
    print(f"{label} (group {gid})")
    print("=" * 70)

    rp = requests.get(f"{TCGCSV_BASE}/{gid}/products", headers=HEADERS, timeout=30)
    products = rp.json()
    if isinstance(products, dict):
        products = products.get("results", products.get("data", []))
    product_names = {p.get('productId'): p.get('name', '') for p in products} if isinstance(products, list) else {}

    time.sleep(0.2)

    rpr = requests.get(f"{TCGCSV_BASE}/{gid}/prices", headers=HEADERS, timeout=30)
    prices = rpr.json()
    if isinstance(prices, dict):
        prices = prices.get("results", prices.get("data", []))

    unmatched = []
    for row in prices:
        pid = row.get("productId")
        if not pid:
            continue
        pid = int(pid)
        if pid not in existing_pids:
            unmatched.append((pid, product_names.get(pid, '(name unknown)'), row.get('subTypeName', '')))

    print(f"Total price entries in this group: {len(prices)}")
    print(f"Unmatched (no DB row at all): {len(unmatched)}")
    print()
    if unmatched:
        # Group by base product_id to avoid listing the same card 3x for N/H/RH subtypes
        seen_pids = {}
        for pid, name, subtype in unmatched:
            seen_pids.setdefault(pid, {'name': name, 'subtypes': []})
            seen_pids[pid]['subtypes'].append(subtype)

        print(f"Unique unmatched products: {len(seen_pids)}")
        print()
        for pid, info in sorted(seen_pids.items()):
            print(f"  product_id={pid} | {info['name']} | subtypes: {info['subtypes']}")
    print()
    time.sleep(0.3)
