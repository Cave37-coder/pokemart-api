"""
delete_confirmed_duplicate_variants.py

Applies the DELETE bucket from classify_wrong_variants.py: 1,384 rows
that are genuine phantom duplicates -- a correctly-labeled sibling row
already exists for that exact product_id, confirmed against LIVE TCGCSV
data (not the stale bible, which was proven wrong for HS Fire Energy and
Skyridge Pikachu earlier tonight).

Per earlier instruction: delete regardless of stock -- flagged separately
in the output so you know which ones had real stock, for your own
records, but not treated as a reason to skip.

Usage:
    python manage.py shell -c "exec(open('delete_confirmed_duplicate_variants.py').read())"

DRY RUN by default -- shows what would be deleted, changes nothing.
Set APPLY = True to actually delete.
"""

import csv
from collections import defaultdict, Counter
from products.models import PokemonProduct

APPLY = True  # flip to True once the dry-run output looks right

TRUTH_CSV_PATH = 'live_variant_truth.csv'

print(f"Mode: {'APPLY (deleting)' if APPLY else 'DRY RUN (no changes will be made)'}")
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

to_delete = []
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
        to_delete.append(p)

print(f"Rows to delete (confirmed genuine duplicates, live-verified): {len(to_delete)}")
print()

by_set = Counter(p.card_set.code for p in to_delete)
print("Breakdown by set:")
for sc, count in by_set.most_common(30):
    print(f"  {sc}: {count}")
print()

with_stock = [p for p in to_delete if getattr(p, 'stock', 0)]
print(f"Of these, {len(with_stock)} have nonzero stock (deleted anyway per instruction, listed here for your records):")
for p in with_stock[:30]:
    print(f"  [{p.card_set.code}] {p.name} -- variant={p.variant_override or 'N'} stock={p.stock} (product_id={p.tcgcsv_product_id})")
print()

print("Sample of all deletions (first 30):")
for p in to_delete[:30]:
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
