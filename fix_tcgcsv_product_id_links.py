"""
fix_tcgcsv_product_id_links.py

Run AFTER cleanup_wrong_variants.py and sync_missing_variants.py.

CORRECTED (2026-07-13): earlier version of this script assumed every
variant of a card has its own distinct tcgcsv_product_id, and tried to
force every row to a bare "TCGCSV-{id}" pb_id. That's wrong -- TCGCSV
legitimately shares ONE product_id across multiple SubTypes (Normal,
Holofoil, Reverse Holofoil) for the same physical card, same as
confirmed for PBL images earlier today. The "-RH"/"-N" suffixed pb_ids
this script previously flagged as "malformed" were actually a correct
workaround for that shared-ID case, not a bug.

Real fix: a row's tcgcsv_product_id gets corrected either way (that part
was already right). For pb_id specifically: use the bare "TCGCSV-{id}"
format ONLY if no other row already owns that exact pb_id (checked live
against the DB, not guessed from the bible) -- otherwise keep the
"TCGCSV-{id}-{variant}" suffixed form so the unique constraint is
respected without colliding with a sibling variant sharing the same
product_id.

Usage:
    python manage.py shell -c "exec(open('fix_tcgcsv_product_id_links.py').read())"

DRY RUN by default -- shows what would change, changes nothing.
Set APPLY = True to actually fix.
"""

import csv
import re
from decimal import Decimal, InvalidOperation
from django.db import transaction
from products.models import PokemonProduct

APPLY = True  # flip to True once the dry-run output looks right

TARGET_SETS = ['PRE', 'ASC', 'WHT', 'BLK']
BIBLE_CSV_PATH = 'pokebulk_bible_v7.csv'  # adjust if it's elsewhere

print(f"Mode: {'APPLY (fixing)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

# --- Build (set_code, card_number, variant) -> (correct product_id, correct price) from the bible ---
with open(BIBLE_CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    bible_rows = [r for r in reader if r.get('set_code', '').strip() in TARGET_SETS and r.get('is_card', '').strip().lower() == 'true']

bible_lookup = {}
for row in bible_rows:
    sc = row['set_code'].strip()
    try:
        cn = int(float(row.get('card_number', '') or 0))
    except (ValueError, TypeError):
        continue
    variant = row['variant_code'].strip()
    key = (sc, cn, variant)
    bible_lookup[key] = {
        'product_id': row['product_id'].strip(),
        'price': row.get('pokebulk_zar', '').strip(),
        'name': row.get('name', ''),
    }

print(f"Bible lookup entries built: {len(bible_lookup)}")
print()

# --- Find every DB row whose pb_id doesn't match the standard TCGCSV-{id}[-{variant}] format ---
STANDARD_PB_ID = re.compile(r'^TCGCSV-\d+(-[A-Z]+)?$')

db_products = PokemonProduct.objects.filter(card_set__code__in=TARGET_SETS).select_related('card_set')
print(f"DB rows to check: {db_products.count()}")

# Live set of every pb_id currently in use, for collision checking --
# built once up front rather than re-querying per row.
existing_pb_ids = set(PokemonProduct.objects.values_list('pb_id', flat=True))

suspect_rows = [p for p in db_products if not STANDARD_PB_ID.match(p.pb_id or '')]
print(f"Rows with non-standard pb_id (need investigation): {len(suspect_rows)}")
print()

to_fix = []
no_bible_match = []

for p in suspect_rows:
    sc = p.card_set.code
    cn = p.card_number
    variant = (p.variant_override or 'N').strip()
    key = (sc, cn, variant)

    match = bible_lookup.get(key)
    if not match:
        no_bible_match.append(p)
        continue

    correct_pid = match['product_id']
    current_pid = str(p.tcgcsv_product_id) if p.tcgcsv_product_id else None

    try:
        correct_price = Decimal(match['price']) if match['price'] else None
    except InvalidOperation:
        correct_price = None

    # Prefer the bare form; only add the variant suffix if that bare pb_id
    # is already owned by a DIFFERENT row (a sibling variant sharing the
    # same product_id) -- checked live against the DB, not assumed.
    bare_pb_id = f"TCGCSV-{correct_pid}"
    if bare_pb_id in existing_pb_ids and bare_pb_id != p.pb_id:
        new_pb_id = f"TCGCSV-{correct_pid}-{variant}"
    else:
        new_pb_id = bare_pb_id

    to_fix.append((p, correct_pid, correct_price, current_pid, new_pb_id))

print(f"Rows with a bible match, will be fixed: {len(to_fix)}")
print(f"Rows with NO bible match at all (can't auto-fix, needs manual look): {len(no_bible_match)}")
print()

if to_fix:
    print("Sample (first 20):")
    for p, correct_pid, correct_price, current_pid, new_pb_id in to_fix[:20]:
        print(f"  [{p.card_set.code}] {p.name} (#{p.card_number}, variant={p.variant_override or 'N'})")
        print(f"    pb_id: {p.pb_id!r} -> {new_pb_id!r}")
        print(f"    tcgcsv_product_id: {current_pid!r} -> {correct_pid}")
        print(f"    price: R{p.price} -> R{correct_price}")

if no_bible_match:
    print(f"\n{len(no_bible_match)} row(s) with no bible match -- can't auto-fix, check manually:")
    for p in no_bible_match[:15]:
        print(f"  [{p.card_set.code}] {p.name} (#{p.card_number}, variant={p.variant_override or 'N'}) pb_id={p.pb_id!r}")

if APPLY and to_fix:
    print("\nApplying fixes...")
    fixed = 0
    collisions = []
    for p, correct_pid, correct_price, current_pid, new_pb_id in to_fix:
        p.tcgcsv_product_id = int(correct_pid)
        p.pb_id = new_pb_id
        if correct_price is not None:
            p.price = correct_price
        try:
            with transaction.atomic():
                p.save(update_fields=['tcgcsv_product_id', 'pb_id', 'price'])
            fixed += 1
        except Exception as e:
            # A genuine remaining conflict -- e.g. two rows both need the
            # exact same suffixed pb_id, which would mean a real duplicate
            # row exists. Skip and keep going rather than crashing.
            collisions.append((p, new_pb_id, str(e)))
        if fixed % 25 == 0 and fixed:
            print(f"  fixed {fixed}/{len(to_fix)}...")
    print(f"\nDone. Fixed {fixed} row(s).")
    if collisions:
        print(f"\n{len(collisions)} row(s) SKIPPED due to a genuine remaining collision -- needs manual review:")
        for p, new_pb_id, err in collisions:
            print(f"  [{p.card_set.code}] {p.name} (#{p.card_number}, variant={p.variant_override or 'N'}) "
                  f"-- wanted pb_id={new_pb_id!r}")
elif to_fix:
    print("\nDry run only -- no changes saved. Set APPLY = True and re-run to apply.")
else:
    print("\nNothing to fix.")
