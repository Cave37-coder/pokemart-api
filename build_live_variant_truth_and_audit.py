"""
build_live_variant_truth_and_audit.py

Step 1 (the "crawl" step): fetch LIVE product + price data directly from
TCGCSV's real API for every set, building a genuinely current truth table
of (set_code, product_id) -> variant_codes actually available. This does
NOT rely on the bible CSV's variant data at all -- only uses the bible to
get the set_code -> group_id mapping (that part is reliable; it's the
per-product subtype completeness that's been proven unreliable for old
sets like HS and Skyridge tonight).

Step 2: save this live truth to a CSV -- this is the "clean up the bible"
deliverable, a corrected reference of real variant existence you can use
to patch pokebulk_bible_v7.csv's variant data going forward.

Step 3 (the "audit", not "walk" yet): compare the DB against this live
truth (not the old bible truth) and report what's genuinely wrong.
Still READ-ONLY / dry-run only -- no deletion capability in this script
at all. Once you've reviewed this output and trust it, a separate
delete script can be pointed at the corrected CSV.

Usage:
    python manage.py shell -c "exec(open('build_live_variant_truth_and_audit.py').read())"

Takes several minutes -- fetches products AND prices per set, live, for
every set in the bible (up to ~147 sets x 2 API calls each).
"""

import csv
import time
import requests
from collections import defaultdict, Counter
from products.models import PokemonProduct

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
BIBLE_CSV_PATH = 'pokebulk_bible_v7.csv'
OUTPUT_CSV_PATH = 'live_variant_truth.csv'

VARIANT_MAP = {
    'Normal': 'N',
    'Holofoil': 'H',
    'Reverse Holofoil': 'RH',
    '1st Edition': 'N',
    '1st Edition Holofoil': 'H',
    'Unlimited': 'N',
    'Unlimited Holofoil': 'H',
}

print("Step 1: Getting set_code -> group_id mapping from bible (this part is reliable)...")
with open(BIBLE_CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    bible_rows = list(reader)

set_to_group = {}
for row in bible_rows:
    sc = row.get('set_code', '').strip()
    raw_gid = row.get('tcgcsv_group_id', '').strip() or row.get('group_id', '').strip()
    if sc and raw_gid and sc not in set_to_group:
        # Bible CSV sometimes stores this as a float-formatted string
        # (e.g. "1402.0") if the column had any blank values elsewhere,
        # which pandas/CSV export coerces the WHOLE column to float for.
        # Normalize to a clean int string either way.
        try:
            gid = str(int(float(raw_gid)))
        except ValueError:
            continue
        set_to_group[sc] = gid

print(f"  {len(set_to_group)} set_code -> group_id mappings found")
print()

print("Step 2: Fetching LIVE product + price data from TCGCSV for each set...")
print("(this is the real ground truth -- not the bible's variant data)")
print()

live_truth = defaultdict(set)  # (set_code, product_id) -> {variant_codes}
live_names = {}  # product_id -> name, for the output CSV
fetch_errors = []

items = sorted(set_to_group.items())
for i, (sc, gid) in enumerate(items, 1):
    try:
        rp = requests.get(f"{TCGCSV_BASE}/{gid}/products", headers=HEADERS, timeout=30)
        products = rp.json()
        if isinstance(products, dict):
            products = products.get("results", products.get("data", []))
        for p in products:
            pid = p.get('productId')
            if pid:
                live_names[pid] = p.get('name', '')

        time.sleep(0.15)

        rpr = requests.get(f"{TCGCSV_BASE}/{gid}/prices", headers=HEADERS, timeout=30)
        prices = rpr.json()
        if isinstance(prices, dict):
            prices = prices.get("results", prices.get("data", []))
        if not isinstance(prices, list):
            fetch_errors.append(sc)
            if len(fetch_errors) <= 5:
                print(f"  [DEBUG] {sc} (group {gid}) returned non-list prices response: {str(prices)[:200]}")
            continue

        for row in prices:
            pid = row.get('productId')
            if not pid:
                continue
            subtype = row.get('subTypeName', 'Normal')
            variant = VARIANT_MAP.get(subtype, subtype)
            live_truth[(sc, str(pid))].add(variant)

    except Exception as e:
        fetch_errors.append(sc)
        if len(fetch_errors) <= 5:
            print(f"  [DEBUG] {sc} (group {gid}) failed: {e}")

    time.sleep(0.15)
    if i % 20 == 0:
        print(f"  ...processed {i}/{len(items)} sets")

print()
print(f"Done fetching. {len(live_truth)} unique (set, product_id) groups with live data.")
print(f"Fetch errors on {len(fetch_errors)} sets: {fetch_errors[:20]}")
print()

# --- Save the corrected reference CSV ---
print(f"Step 3: Saving corrected reference to {OUTPUT_CSV_PATH}...")
with open(OUTPUT_CSV_PATH, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['set_code', 'product_id', 'name', 'variant_codes'])
    for (sc, pid), variants in sorted(live_truth.items()):
        name = live_names.get(int(pid), '') if pid.isdigit() else ''
        writer.writerow([sc, pid, name, ','.join(sorted(variants))])
print(f"  Saved {len(live_truth)} rows.")
print()

# --- Step 4: Audit the DB against this LIVE truth (still read-only) ---
print("Step 4: Auditing DB against LIVE truth (read-only, no deletion)...")
target_sets = list(set_to_group.keys())
db_products = PokemonProduct.objects.filter(card_set__code__in=target_sets).select_related('card_set')
print(f"DB rows checked: {db_products.count()}")
print()

genuinely_wrong = []
no_live_data = []

for p in db_products:
    sc = p.card_set.code
    pid = str(p.tcgcsv_product_id) if p.tcgcsv_product_id else None
    variant = (p.variant_override or 'N').strip()

    key = (sc, pid)
    if key not in live_truth:
        no_live_data.append(p)
        continue

    if variant not in live_truth[key]:
        genuinely_wrong.append(p)

print(f"Rows genuinely wrong per LIVE TCGCSV data: {len(genuinely_wrong)}")
print(f"Rows with no live data at all (product may be delisted/renumbered): {len(no_live_data)}")
print()

by_set = Counter(p.card_set.code for p in genuinely_wrong)
print("Breakdown by set (genuinely wrong, live-verified):")
for sc, count in by_set.most_common(30):
    print(f"  {sc}: {count}")
print()

print("Sample (first 30) -- these are now LIVE-VERIFIED, not bible-guessed:")
for p in genuinely_wrong[:30]:
    print(f"  [{p.card_set.code}] {p.name} -- variant={p.variant_override or 'N'} (product_id={p.tcgcsv_product_id})")

print()
print("This script made NO changes. Review the above, spot-check a few of these")
print("directly (same way HS Fire Energy and Skyridge Pikachu were checked)")
print("before building a delete step against this corrected data.")
