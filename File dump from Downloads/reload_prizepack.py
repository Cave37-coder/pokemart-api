import csv
import re
from products.models import CardSet, PokemonProduct, Era, Category
from django.db import transaction

CSV_PATH = r'pokebulk_cards_20260524_1558.csv'

RARITY_MAP = {
    'Common': 'common', 'Uncommon': 'uncommon', 'Rare': 'rare',
    'Holo Rare': 'holo_rare', 'Ultra Rare': 'ultra_rare',
    'Secret Rare': 'secret_rare', 'Promo': 'promo',
    'Illustration Rare': 'illustration_rare',
    'Special Illustration Rare': 'special_illustration_rare',
    'Hyper Rare': 'hyper_rare', 'Rare Holo': 'holo_rare',
    'Rare Ultra': 'ultra_rare', 'Rare Secret': 'secret_rare',
    'Amazing Rare': 'ultra_rare', 'Radiant Rare': 'ultra_rare',
    'Double Rare': 'ultra_rare', 'ACE SPEC Rare': 'ultra_rare',
    'Shiny Rare': 'ultra_rare', 'Shiny Ultra Rare': 'secret_rare',
    'Trainer Gallery Rare Holo': 'holo_rare',
    'Classic Collection': 'ultra_rare',
}

VARIANT_MAP = {
    'Holofoil': 'H', 'Reverse Holofoil': 'RH', 'Normal': 'N',
    'H': 'H', 'N': 'N', 'RH': 'RH',
}

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
pokemon_cat = Category.objects.filter(name='Pokemon').first()

# Get or create all sets
orig_set = CardSet.objects.get(code='PRIZEPACK')
pps_set_map = {'': orig_set}

for label, (code, name, release) in PPS_SETS.items():
    cs, created = CardSet.objects.get_or_create(
        code=code,
        defaults={'name': name, 'era': sv_era, 'release_date': release,
                  'symbol_url': orig_set.symbol_url or '',
                  'logo_url': orig_set.logo_url or '',
                  'regulation_mark': 'G'}
    )
    pps_set_map[label] = cs
    print(f"  {'Created' if created else 'Exists'}: {code}")

# Step 1: Delete all existing PRIZEPACK cards (not bundles, not the PPS sets)
all_pps_codes = ['PRIZEPACK'] + [code for code, name, release in PPS_SETS.values()]
deleted = PokemonProduct.objects.filter(
    card_set__code__in=all_pps_codes
).exclude(variant_override='BUNDLE').delete()
print(f"\nDeleted: {deleted}")

# Step 2: Read CSV and create fresh
print("\nReading CSV and creating products...")
created_count = 0
skipped = 0

with open(CSV_PATH, encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) < 5 or row[2].strip() != 'PRIZEPACK':
            continue

        full_name = row[5].strip()
        clean_name = row[6].strip() or full_name
        card_num_raw = row[7].strip()
        rarity_raw = row[8].strip()
        variant_raw = row[24].strip() if len(row) > 24 else 'N'
        series_label = row[23].strip() if len(row) > 23 else ''

        # Extract series from name if not in col23
        if not series_label.startswith('Prize Pack Series'):
            m = re.search(r'Prize Pack Series (\d+)', full_name)
            if m:
                series_label = f'Prize Pack Series {m.group(1)}'

        # Determine target set
        target_set = pps_set_map.get(series_label, orig_set)

        # Parse card number
        card_num = None
        if card_num_raw:
            num_part = card_num_raw.split('/')[0].strip()
            try:
                card_num = int(re.sub(r'[^0-9]', '', num_part))
            except:
                pass

        # Prices
        def safe_float(v):
            try: return float(v.strip()) if v.strip() else None
            except: return None

        price = safe_float(row[15]) if len(row) > 15 else None
        if not price:
            price = safe_float(row[16]) if len(row) > 16 else None
        if not price:
            price = 0.00

        rarity = RARITY_MAP.get(rarity_raw, 'common')
        variant = VARIANT_MAP.get(variant_raw, 'N')

        # Build pb_id
        set_code = target_set.code
        pb_id = f"{set_code}-{card_num or 0}-{variant}"

        # Skip if already exists
        if PokemonProduct.objects.filter(pb_id=pb_id).exists():
            skipped += 1
            continue

        try:
            PokemonProduct.objects.create(
                pb_id=pb_id,
                name=clean_name,
                card_set=target_set,
                category=pokemon_cat,
                card_number=card_num,
                rarity=rarity,
                variant_override=variant,
                price=price,
                stock=0,
                is_active=True,
            )
            created_count += 1
        except Exception as e:
            print(f"  Error: {clean_name} — {e}")
            skipped += 1

print(f"\nCreated: {created_count} | Skipped: {skipped}")

# Summary per set
for label, cs in pps_set_map.items():
    count = PokemonProduct.objects.filter(card_set=cs).exclude(variant_override='BUNDLE').count()
    if count > 0:
        print(f"  {cs.code}: {count} cards")
