"""
check_pbl_pricing_sync.py
Read-only diagnostic. Checks whether PBL has the same pb_id/tcgcsv_product_id
linking problem found and fixed tonight for PRE/ASC/WHT/BLK (non-standard
pb_id -> daily sync can't match it -> price frozen since creation).

Also compares current DB prices against the bible CSV's pokebulk_zar
column to see if there's already a real mismatch, independent of the
pb_id format question.

Usage:
    python manage.py shell -c "exec(open('check_pbl_pricing_sync.py').read())"
"""

import re
import csv
from products.models import PokemonProduct

STANDARD_PB_ID = re.compile(r'^TCGCSV-\d+(-[A-Z]+)?$')
BIBLE_CSV_PATH = 'pokebulk_bible_v7.csv'  # adjust if it's elsewhere

products = PokemonProduct.objects.filter(card_set__code='PBL').select_related('card_set')
total = products.count()
print(f"Total PBL rows: {total}")
print()

# --- Check 1: non-standard pb_id (same check as fix_tcgcsv_product_id_links.py) ---
non_standard = [p for p in products if not STANDARD_PB_ID.match(p.pb_id or '')]
print(f"Rows with non-standard pb_id (won't be found by daily sync): {len(non_standard)}")
if non_standard:
    print("Sample (first 15):")
    for p in non_standard[:15]:
        print(f"  {p.name} (#{p.card_number}, {p.variant_override or 'N'}) -- pb_id={p.pb_id!r} tcgcsv_product_id={p.tcgcsv_product_id}")
print()

# --- Check 2: missing tcgcsv_product_id entirely ---
missing_pid = products.filter(tcgcsv_product_id__isnull=True)
print(f"Rows with NO tcgcsv_product_id at all: {missing_pid.count()}")
print()

# --- Check 3: last updated_at spread -- are prices genuinely frozen since creation? ---
from django.db.models import Min, Max
dates = products.aggregate(earliest=Min('updated_at'), latest=Max('updated_at'))
print(f"updated_at range across all PBL rows: {dates['earliest']} to {dates['latest']}")
same_timestamp_count = products.filter(updated_at=dates['earliest']).count()
print(f"Rows still at the EARLIEST updated_at timestamp (never touched since): {same_timestamp_count}/{total}")
print()

# --- Check 4: compare current DB price vs bible's pokebulk_zar for a sample ---
try:
    with open(BIBLE_CSV_PATH, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        bible_rows = {row['product_id'].strip(): row for row in reader if row.get('set_code', '').strip() == 'PBL'}

    mismatches = 0
    checked = 0
    for p in products:
        pid = str(p.tcgcsv_product_id) if p.tcgcsv_product_id else None
        if not pid or pid not in bible_rows:
            continue
        checked += 1
        bible_price = bible_rows[pid].get('pokebulk_zar', '').strip()
        if bible_price and str(p.price) != bible_price:
            mismatches += 1

    print(f"Checked {checked} rows against bible pricing -- {mismatches} price mismatches found")
    print("(Note: bible pricing may itself be a pre-release estimate, not necessarily 'correct' --")
    print(" this just shows whether DB price matches whatever the bible currently has, not ground truth.)")
except FileNotFoundError:
    print(f"Could not find {BIBLE_CSV_PATH} to compare against -- skipping price comparison check.")
