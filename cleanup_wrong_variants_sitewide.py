"""
cleanup_wrong_variants_sitewide.py

Generalized version of cleanup_wrong_variants.py (built for PRE/ASC/WHT/BLK
earlier) -- runs the SAME logic across every set covered by the bible CSV,
since the same phantom-variant bug (extra rows for variants that don't
actually exist per TCGCSV, e.g. a Common card wrongly getting a Holo row)
appears to also affect older WotC-era sets like BSS.

SAFETY: much bigger blast radius than the 4-set version. Dry-run ALWAYS
shows a full per-set breakdown before you decide what to apply -- review
that breakdown carefully. Consider running with ONLY_SETS to test on
a handful of sets first before a full sitewide apply.

Usage:
    python manage.py shell -c "exec(open('cleanup_wrong_variants_sitewide.py').read())"

DRY RUN by default -- shows what would be deleted, changes nothing.
Set APPLY = True to actually delete.
Set ONLY_SETS to a list like ['BSS','BS','JU'] to scope to specific sets
first, instead of literally everything, before trusting a full run.
"""

import csv
from collections import defaultdict, Counter
from products.models import PokemonProduct

APPLY = False  # flip to True once the dry-run output looks right
ONLY_SETS = None  # e.g. ['BSS', 'BS', 'JU'] to test on a few sets first; None = all sets in the bible

BIBLE_CSV_PATH = 'pokebulk_bible_v7.csv'  # adjust if it's elsewhere

print(f"Mode: {'APPLY (deleting)' if APPLY else 'DRY RUN (no changes will be made)'}")
print(f"Scope: {'ALL sets in bible' if not ONLY_SETS else ONLY_SETS}")
print()

with open(BIBLE_CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    bible_rows = list(reader)

if ONLY_SETS:
    bible_rows = [r for r in bible_rows if r.get('set_code', '').strip() in ONLY_SETS]

target_sets = sorted(set(r['set_code'].strip() for r in bible_rows if r.get('set_code', '').strip()))
print(f"Sets covered by bible (and therefore checked): {len(target_sets)}")
print()

truth = defaultdict(set)
for row in bible_rows:
    sc = row['set_code'].strip()
    pid = row['product_id'].strip()
    vc = row['variant_code'].strip()
    if pid and vc:
        truth[(sc, pid)].add(vc)

print(f"Unique (set, product_id) groups in bible: {len(truth)}")
print()

db_products = PokemonProduct.objects.filter(card_set__code__in=target_sets).select_related('card_set')
print(f"DB rows to check: {db_products.count()}")
print()

to_delete = []
no_tcgcsv_data_at_all = []
energy_flagged_for_review = []

for p in db_products:
    sc = p.card_set.code
    pid = str(p.tcgcsv_product_id) if p.tcgcsv_product_id else None
    variant = (p.variant_override or 'N').strip()

    key = (sc, pid)
    if key not in truth:
        no_tcgcsv_data_at_all.append(p)
        continue

    if variant not in truth[key]:
        # CONFIRMED 2026-07-17 via direct TCGplayer/retailer research: the
        # bible's own data has a gap for Basic Energy Reverse Holo variants
        # (e.g. HS Fire Energy 116/123 genuinely has an RH print that TCGCSV's
        # export didn't capture) -- this is a bible/source data problem, not
        # a wrong DB row. Never auto-delete Energy cards; flag for manual
        # review instead.
        if 'energy' in (p.name or '').lower():
            energy_flagged_for_review.append(p)
        else:
            to_delete.append(p)

print(f"Rows to delete (wrong variant, per TCGCSV): {len(to_delete)}")
print(f"Energy cards SKIPPED from auto-delete (bible has a confirmed gap here, needs manual review): {len(energy_flagged_for_review)}")
print(f"Rows with no TCGCSV data at all for that product_id (skipped, can't judge): {len(no_tcgcsv_data_at_all)}")
print()

if energy_flagged_for_review:
    energy_by_set = Counter(p.card_set.code for p in energy_flagged_for_review)
    print("Energy cards flagged for manual review, by set:")
    for sc, count in energy_by_set.most_common():
        print(f"  {sc}: {count}")
    print()

del_by_set = Counter(p.card_set.code for p in to_delete)
print("Breakdown by set (ALL sets with at least one row to delete):")
for sc, count in del_by_set.most_common():
    print(f"  {sc}: {count}")
print()

if to_delete:
    print("Sample of rows to delete (first 30):")
    for p in to_delete[:30]:
        print(f"  [{p.card_set.code}] {p.name} -- variant={p.variant_override or 'N'} (product_id={p.tcgcsv_product_id})")

if APPLY and to_delete:
    print("\nDeleting...")
    ids = [p.id for p in to_delete]
    deleted_count, _ = PokemonProduct.objects.filter(id__in=ids).delete()
    print(f"Done. Deleted {deleted_count} row(s).")
elif to_delete:
    print("\nDry run only -- no rows deleted. Review the per-set breakdown above,")
    print("then set APPLY = True (optionally with ONLY_SETS scoped down first) and re-run.")
else:
    print("\nNothing to delete.")
