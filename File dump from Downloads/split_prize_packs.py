import csv
import re
from products.models import CardSet, PokemonProduct, Era
from django.db import transaction

CSV_PATH = r'pokebulk_cards_20260524_1558.csv'

PPS_SETS = {
    'Prize Pack Series 1': ('PPS1', 'Prize Pack Series 1', '2022-11-09'),
    'Prize Pack Series 2': ('PPS2', 'Prize Pack Series 2', '2023-01-19'),
    'Prize Pack Series 3': ('PPS3', 'Prize Pack Series 3', '2023-08-14'),
    'Prize Pack Series 4': ('PPS4', 'Prize Pack Series 4', '2024-02-14'),
    'Prize Pack Series 5': ('PPS5', 'Prize Pack Series 5', '2024-08-01'),
    'Prize Pack Series 6': ('PPS6', 'Prize Pack Series 6', '2024-11-01'),
    'Prize Pack Series 7': ('PPS7', 'Prize Pack Series 7', '2025-02-01'),
    'Prize Pack Series 8': ('PPS8', 'Prize Pack Series 8', '2025-08-01'),
}

sv_era = Era.objects.filter(code='B8').first()
orig_set = CardSet.objects.get(code='PRIZEPACK')

pps_set_map = {}
for series_label, (code, name, release) in PPS_SETS.items():
    cs, _ = CardSet.objects.get_or_create(
        code=code,
        defaults={'name': name, 'era': sv_era, 'release_date': release,
                  'symbol_url': orig_set.symbol_url or '', 'logo_url': orig_set.logo_url or '',
                  'regulation_mark': 'G'}
    )
    pps_set_map[series_label] = cs

# Read CSV - use full_name (col 5) which contains "(Prize Pack Series X)"
# Also use col 23 as fallback
# Build: (card_num_int, H_or_N) -> series
print("Reading CSV...")
num_var_to_series = {}
name_to_series = {}

with open(CSV_PATH, encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) < 5 or row[2].strip() != 'PRIZEPACK':
            continue
        full_name = row[5].strip()  # e.g. "Charizard V (Prize Pack Series 1)"
        col23 = row[23].strip() if len(row) > 23 else ''
        variant = row[24].strip() if len(row) > 24 else 'N'

        # Extract series from name
        series = None
        m = re.search(r'Prize Pack Series (\d+)', full_name)
        if m:
            series = f'Prize Pack Series {m.group(1)}'
        elif col23.startswith('Prize Pack Series'):
            series = col23

        if not series:
            continue

        # Also extract card number from col 7
        card_num_raw = row[7].strip().split('/')[0].strip()
        try:
            card_num = int(re.sub(r'[^0-9]', '', card_num_raw))
        except:
            card_num = None

        # Clean base name (remove the "(Prize Pack Series X)" part)
        base_name = re.sub(r'\s*\(Prize Pack Series \d+\)', '', full_name).strip()

        if card_num is not None:
            key = (card_num, variant)
            num_var_to_series[key] = series
        name_to_series[(base_name, variant)] = series

print(f"Num+variant mappings: {len(num_var_to_series)}")
print(f"Name+variant mappings: {len(name_to_series)}")
print(f"Unique series: {sorted(set(num_var_to_series.values()) | set(name_to_series.values()))}")

# Move products
products = PokemonProduct.objects.filter(card_set=orig_set).exclude(variant_override='BUNDLE')
moved = {}
not_found_list = []

with transaction.atomic():
    for product in products:
        cn = product.card_number
        var_code = product.variant_override or 'N'
        # Map variant to H or N
        var = 'N' if var_code == 'N' else 'H'

        # Try card_num + variant first
        series = num_var_to_series.get((cn, var))

        # Try name + variant
        if not series:
            base = re.sub(r'\s*\(Prize Pack Series \d+\)', '', product.name).strip()
            series = name_to_series.get((base, var)) or name_to_series.get((product.name, var))

        if series and series in pps_set_map:
            product.card_set = pps_set_map[series]
            product.save(update_fields=['card_set'])
            moved[series] = moved.get(series, 0) + 1
        else:
            not_found_list.append(f"{product.name} #{cn} {var_code}")

print("\nResults:")
for s, c in sorted(moved.items()):
    print(f"  {s}: {c} cards moved")
print(f"  Remaining in PRIZEPACK: {len(not_found_list)}")
if not_found_list[:5]:
    print(f"  Sample unmatched: {not_found_list[:5]}")
