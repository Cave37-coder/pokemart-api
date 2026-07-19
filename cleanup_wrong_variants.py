"""
cleanup_wrong_variants.py

Cross-references every PokemonProduct row in PRE, ASC, WHT, BLK against
TCGCSV's authoritative variant data (via the bible CSV) and deletes any
row whose (product_id, variant) combination doesn't actually exist in
TCGCSV -- these are erroneous rows that got created somewhere along the
line, causing wrong price lookups (e.g. Exeggcute has real TCGCSV
variants N+RH only, but the DB had 5 rows including phantom H/PBP/MBP --
those phantom rows were pulling wrong prices into stock counts).

Per explicit instruction (2026-07-13): delete ALL wrong-variant rows
regardless of stock -- Michael will manually recount physical stock
after cleanup, since getting the correct variant/pricing data is more
urgent than preserving stock counts on rows that shouldn't exist at all.

Usage:
    python manage.py shell -c "exec(open('cleanup_wrong_variants.py').read())"

DRY RUN by default -- shows what would be deleted, changes nothing.
Set APPLY = True to actually delete.
"""

import csv
from collections import defaultdict
from products.models import PokemonProduct

APPLY = False  # flip to True once the dry-run output looks right

TARGET_SETS = ['PRE', 'ASC', 'WHT', 'BLK']
BIBLE_CSV_PATH = 'pokebulk_bible_v7.csv'  # adjust if it's elsewhere

print(f"Mode: {'APPLY (deleting)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

# --- Build the truth set from the bible: (set_code, tcgcsv_product_id) -> valid variant codes ---
with open(BIBLE_CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    bible_rows = [r for r in reader if r.get('set_code', '').strip() in TARGET_SETS]

truth = defaultdict(set)
for row in bible_rows:
    sc = row['set_code'].strip()
    pid = row['product_id'].strip()
    vc = row['variant_code'].strip()
    if pid and vc:
        truth[(sc, pid)].add(vc)

print(f"Bible rows loaded for {TARGET_SETS}: {len(bible_rows)}")
print(f"Unique (set, product_id) groups: {len(truth)}")
print()

# --- Check every DB row against the truth set ---
db_products = PokemonProduct.objects.filter(card_set__code__in=TARGET_SETS).select_related('card_set')
print(f"DB rows to check: {db_products.count()}")
print()

to_delete = []
no_tcgcsv_data_at_all = []

for p in db_products:
    sc = p.card_set.code
    pid = str(p.tcgcsv_product_id) if p.tcgcsv_product_id else None
    variant = (p.variant_override or 'N').strip()

    key = (sc, pid)
    if key not in truth:
        # No TCGCSV data at all for this product_id -- can't judge, flag separately, don't delete
        no_tcgcsv_data_at_all.append(p)
        continue

    if variant not in truth[key]:
        to_delete.append(p)

print(f"Rows to delete (wrong variant, per TCGCSV): {len(to_delete)}")
print(f"Rows with no TCGCSV data at all for that product_id (can't judge, skipped): {len(no_tcgcsv_data_at_all)}")
print()

# Breakdown per set
from collections import Counter
del_by_set = Counter(p.card_set.code for p in to_delete)
for sc in TARGET_SETS:
    print(f"  {sc}: {del_by_set.get(sc, 0)} rows to delete")
print()

if to_delete:
    print("Sample of rows to delete (first 20):")
    for p in to_delete[:20]:
        stock_note = f" (had stock -- will need manual recount)" if getattr(p, 'stock', 0) else ""
        print(f"  [{p.card_set.code}] {p.name} -- variant={p.variant_override or 'N'} (product_id={p.tcgcsv_product_id}){stock_note}")

if no_tcgcsv_data_at_all:
    print(f"\n{len(no_tcgcsv_data_at_all)} rows skipped -- no TCGCSV data at all for that product_id. Sample:")
    for p in no_tcgcsv_data_at_all[:10]:
        print(f"  [{p.card_set.code}] {p.name} -- variant={p.variant_override or 'N'} (product_id={p.tcgcsv_product_id})")

if APPLY and to_delete:
    print("\nDeleting...")
    ids = [p.id for p in to_delete]
    deleted_count, _ = PokemonProduct.objects.filter(id__in=ids).delete()
    print(f"Done. Deleted {deleted_count} row(s).")
elif to_delete:
    print("\nDry run only -- no rows deleted. Set APPLY = True and re-run to apply.")
else:
    print("\nNothing to delete.")
