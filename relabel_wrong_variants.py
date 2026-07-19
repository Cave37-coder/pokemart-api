"""
relabel_wrong_variants.py

Applies the RELABEL bucket from classify_wrong_variants.py: 1,348 rows
that are real products with the wrong variant_override code (e.g. PBL
Mega Darkrai ex 120/084 stored as 'N' when it's actually a foil-only
'H' print). Updates variant_override and variant_sort only -- does NOT
touch price, stock, images, or anything else, and does NOT delete
anything.

Price note: after relabeling, the row's variant_override will correctly
match what TCGCSV calls it, so the next scheduled sync_prices_only run
will naturally pick up and correct its price automatically (it matches
by (product_id, variant_override)) -- no need to fetch/set price here.

Usage:
    python manage.py shell -c "exec(open('relabel_wrong_variants.py').read())"

DRY RUN by default -- shows what would change, changes nothing.
Set APPLY = True to actually update.
"""

import csv
from collections import defaultdict
from products.models import PokemonProduct

APPLY = True  # flip to True once the dry-run output looks right

TRUTH_CSV_PATH = 'live_variant_truth.csv'

VARIANT_ORDER = [
    "N", "H", "RH",
    "PB", "MB", "LB", "FB", "QB", "UB", "DB",
    "TR", "SE", "PBP", "MBP", "CC", "TT",
    "EX", "CH",
]
VARIANT_SORT_MAP = {code: i for i, code in enumerate(VARIANT_ORDER)}

print(f"Mode: {'APPLY (relabeling)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

live_truth = defaultdict(set)
with open(TRUTH_CSV_PATH, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sc = row['set_code'].strip()
        pid = row['product_id'].strip()
        variants = [v.strip() for v in row['variant_codes'].split(',') if v.strip()]
        live_truth[(sc, pid)].update(variants)

all_db_rows = list(PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True).select_related('card_set'))
db_variants_by_product = defaultdict(set)
for p in all_db_rows:
    key = (p.card_set.code, str(p.tcgcsv_product_id))
    db_variants_by_product[key].add((p.variant_override or 'N').strip())

to_relabel = []
for p in all_db_rows:
    sc = p.card_set.code
    pid = str(p.tcgcsv_product_id)
    variant = (p.variant_override or 'N').strip()
    key = (sc, pid)

    if key not in live_truth:
        continue
    correct_variants = live_truth[key]
    if variant in correct_variants:
        continue

    existing = db_variants_by_product[key]
    already_covered = existing & correct_variants
    if already_covered:
        continue  # this is a DELETE candidate, not a relabel -- handled separately
    if len(correct_variants) != 1:
        continue  # ambiguous, skip

    to_relabel.append((p, list(correct_variants)[0]))

print(f"Rows to relabel: {len(to_relabel)}")
print()
print("Sample (first 20):")
for p, new_variant in to_relabel[:20]:
    old = p.variant_override or 'N'
    print(f"  [{p.card_set.code}] {p.name} -- '{old}' -> '{new_variant}' (product_id={p.tcgcsv_product_id})")

if APPLY and to_relabel:
    print("\nApplying relabels...")
    updated = 0
    for p, new_variant in to_relabel:
        p.variant_override = new_variant
        p.variant_sort = VARIANT_SORT_MAP.get(new_variant, 99)
        p.save(update_fields=['variant_override', 'variant_sort'])
        updated += 1
        if updated % 100 == 0:
            print(f"  relabeled {updated}/{len(to_relabel)}...")
    print(f"\nDone. Relabeled {updated} row(s).")
    print("Prices for these will correct automatically on the next scheduled sync_prices_only run.")
elif to_relabel:
    print("\nDry run only -- no changes saved. Set APPLY = True and re-run to apply.")
else:
    print("\nNothing to relabel.")
