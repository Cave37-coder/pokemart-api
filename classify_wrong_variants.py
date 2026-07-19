"""
classify_wrong_variants.py

Follow-up to build_live_variant_truth_and_audit.py. That script correctly
found 2,732 rows where variant_override doesn't match live TCGCSV data --
but "wrong variant" splits into two very different cases needing opposite
fixes:

  1. PHANTOM DUPLICATE: a row that shouldn't exist at all -- a sibling
     row with the CORRECT variant already exists for that product_id.
     Safe to delete.

  2. MISLABELED REAL PRODUCT: the row IS the genuine card, just tagged
     with the wrong variant code, and no correctly-labeled sibling
     exists. Confirmed real example: PBL Mega Darkrai ex 120/084 (a
     $996 Mega Hyper Rare, gold-foil-only print) was stored as
     variant='N' when it should be 'H' -- there is no non-foil print of
     this card at all. Deleting this would destroy a real, valuable
     product row (price, image, everything). The fix is to RELABEL
     variant_override, not delete.

This script reads live_variant_truth.csv (built by the previous script)
and classifies every "wrong" row into one bucket or the other. Still
READ-ONLY -- no changes made. Once you review this split, two separate
next steps become safe: a relabel script for bucket 2, and a delete
script for bucket 1 only.

Usage:
    python manage.py shell -c "exec(open('classify_wrong_variants.py').read())"
"""

import csv
from collections import defaultdict, Counter
from products.models import PokemonProduct

TRUTH_CSV_PATH = 'live_variant_truth.csv'

print("Loading live variant truth...")
live_truth = defaultdict(set)
with open(TRUTH_CSV_PATH, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sc = row['set_code'].strip()
        pid = row['product_id'].strip()
        variants = [v.strip() for v in row['variant_codes'].split(',') if v.strip()]
        live_truth[(sc, pid)].update(variants)

print(f"  {len(live_truth)} (set, product_id) groups loaded")
print()

# Build a lookup of what variant_override values currently exist in the DB
# per (set, product_id), so we can tell if a correctly-labeled sibling
# already exists for any given "wrong" row.
print("Building current DB variant map per (set, product_id)...")
all_db_rows = PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True).select_related('card_set')
db_variants_by_product = defaultdict(set)
db_rows_by_key = defaultdict(list)
for p in all_db_rows:
    key = (p.card_set.code, str(p.tcgcsv_product_id))
    variant = (p.variant_override or 'N').strip()
    db_variants_by_product[key].add(variant)
    db_rows_by_key[key].append(p)

print(f"  {len(db_variants_by_product)} (set, product_id) groups in DB")
print()

relabel_candidates = []
delete_candidates = []
unclear = []

for p in all_db_rows:
    sc = p.card_set.code
    pid = str(p.tcgcsv_product_id)
    variant = (p.variant_override or 'N').strip()
    key = (sc, pid)

    if key not in live_truth:
        continue  # no live data at all, can't judge -- handled separately

    correct_variants = live_truth[key]
    if variant in correct_variants:
        continue  # this row is fine

    # This row's variant is wrong. Does a sibling row already correctly
    # cover one of the live-truth variants for this same product_id?
    existing_variants_for_product = db_variants_by_product[key]
    already_covered = existing_variants_for_product & correct_variants

    if already_covered:
        # A correct sibling already exists -- this row is a redundant duplicate
        delete_candidates.append((p, correct_variants))
    elif len(correct_variants) == 1:
        # No correct sibling exists, and there's exactly one right answer --
        # safe, unambiguous relabel target
        relabel_candidates.append((p, list(correct_variants)[0]))
    else:
        # No correct sibling, but multiple possible live variants -- ambiguous,
        # needs a human decision, don't guess
        unclear.append((p, correct_variants))

print("=" * 70)
print(f"RELABEL candidates (real product, wrong code, safe auto-fix): {len(relabel_candidates)}")
print(f"DELETE candidates (genuine phantom duplicate, sibling already correct): {len(delete_candidates)}")
print(f"UNCLEAR (multiple possible variants, needs manual decision): {len(unclear)}")
print("=" * 70)
print()

by_set_relabel = Counter(p.card_set.code for p, _ in relabel_candidates)
print("RELABEL candidates by set (top 20):")
for sc, count in by_set_relabel.most_common(20):
    print(f"  {sc}: {count}")
print()

print("Sample RELABEL candidates (first 20):")
for p, correct_variant in relabel_candidates[:20]:
    print(f"  [{p.card_set.code}] {p.name} -- '{p.variant_override or 'N'}' -> '{correct_variant}' (product_id={p.tcgcsv_product_id})")
print()

by_set_delete = Counter(p.card_set.code for p, _ in delete_candidates)
print("DELETE candidates by set (top 20):")
for sc, count in by_set_delete.most_common(20):
    print(f"  {sc}: {count}")
print()

print("Sample DELETE candidates (first 20):")
for p, correct_variants in delete_candidates[:20]:
    print(f"  [{p.card_set.code}] {p.name} -- variant={p.variant_override or 'N'} is redundant, sibling already has {correct_variants} (product_id={p.tcgcsv_product_id})")
print()

if unclear:
    print(f"UNCLEAR sample (first 10) -- needs manual review, not auto-fixable either way:")
    for p, correct_variants in unclear[:10]:
        print(f"  [{p.card_set.code}] {p.name} -- currently '{p.variant_override or 'N'}', live truth says one of {correct_variants} (product_id={p.tcgcsv_product_id})")

print()
print("No changes made. This is a classification report only.")
