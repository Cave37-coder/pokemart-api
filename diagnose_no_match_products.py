"""
diagnose_no_match_products.py
Read-only. Replicates sync_prices_only.py's matching logic, but instead of
just counting "no match" entries, records what they actually ARE --
categorized by likely product type (sealed vs single, based on name
keywords) and by which TCGCSV group they belong to. This tells us whether
the 7,934 unmatched products are missing singles worth importing, or
sealed product/other categories PokeBulk doesn't carry anyway.

Usage:
    python manage.py shell -c "exec(open('diagnose_no_match_products.py').read())"

Takes a couple minutes (fetches products AND prices per group, not just
prices, to get real product names for categorization).
"""

import requests
import time
from collections import Counter, defaultdict
from products.models import PokemonProduct

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

SEALED_KEYWORDS = [
    'booster box', 'booster pack', 'elite trainer box', 'etb',
    'bundle', 'blister', 'tin', 'collection box', 'premium collection',
    'build & battle', 'build and battle', 'theme deck', 'starter deck',
    'battle deck', 'sleeved booster', 'booster bundle', 'display box',
    'case', 'binder', 'portfolio', 'playmat', 'deck box',
]

def is_likely_sealed(name):
    n = (name or '').lower()
    return any(kw in n for kw in SEALED_KEYWORDS)

print("Building existing product_id set from DB...")
existing_pids = set(
    PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True)
    .values_list('tcgcsv_product_id', flat=True)
)
print(f"  {len(existing_pids):,} distinct product_ids already in DB")
print()

print("Fetching groups from TCGCSV...")
r = requests.get(f"{TCGCSV_BASE}/groups", headers=HEADERS, timeout=30)
groups = r.json()
if isinstance(groups, dict):
    groups = groups.get("results", groups.get("data", []))
print(f"  {len(groups)} groups found")
print()

no_match_sealed = 0
no_match_single = 0
by_group = Counter()
sample_singles = []
sample_sealed = []

for i, g in enumerate(groups, 1):
    gid = g.get("groupId") or g.get("id")
    gname = g.get("name", f"group_{gid}")

    try:
        rp = requests.get(f"{TCGCSV_BASE}/{gid}/products", headers=HEADERS, timeout=30)
        products = rp.json()
        if isinstance(products, dict):
            products = products.get("results", products.get("data", []))
        product_names = {p.get('productId'): p.get('name', '') for p in products} if isinstance(products, list) else {}

        rpr = requests.get(f"{TCGCSV_BASE}/{gid}/prices", headers=HEADERS, timeout=30)
        prices = rpr.json()
        if isinstance(prices, dict):
            prices = prices.get("results", prices.get("data", []))
        if not isinstance(prices, list):
            continue
    except Exception:
        continue

    for row in prices:
        pid = row.get("productId")
        if not pid:
            continue
        pid = int(pid)
        if pid in existing_pids:
            continue  # matched, not our concern here

        name = product_names.get(pid, '')
        if is_likely_sealed(name):
            no_match_sealed += 1
            by_group[gname] += 1
            if len(sample_sealed) < 20:
                sample_sealed.append((gname, name, pid))
        else:
            no_match_single += 1
            by_group[gname] += 1
            if len(sample_singles) < 30:
                sample_singles.append((gname, name, pid))

    time.sleep(0.15)
    if i % 25 == 0:
        print(f"  ...processed {i}/{len(groups)} groups")

print()
print("=" * 60)
print(f"Total unmatched, likely SEALED product: {no_match_sealed:,}")
print(f"Total unmatched, likely SINGLE card:    {no_match_single:,}")
print("=" * 60)
print()

print("Top 20 groups by unmatched count:")
for gname, count in by_group.most_common(20):
    print(f"  {gname}: {count}")
print()

print("Sample unmatched SINGLES (first 30) -- these are the ones worth reviewing:")
for gname, name, pid in sample_singles:
    print(f"  [{gname}] {name} (product_id={pid})")
print()

print("Sample unmatched SEALED products (first 20) -- likely intentionally not carried:")
for gname, name, pid in sample_sealed:
    print(f"  [{gname}] {name} (product_id={pid})")
