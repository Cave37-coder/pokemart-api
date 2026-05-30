import csv
import re
from products.models import CardSet, PokemonProduct, Era, Category
from django.db import transaction

CSV_PATH = r'pokebulk_cards_20260524_1558.csv'

# Map card total (/XXX) to Prize Pack Series
# Based on Bulbapedia descriptions:
# PPS1: SWSH01-SWSH07 (SwSh through Evolving Skies) + SWSH Promos
# PPS2: SWSH09-SWSH12pt5 (Brilliant Stars through Crown Zenith)  
# PPS3: SWSH09-SV01 (Brilliant Stars through Scarlet & Violet)
# PPS4: SV02-SV03pt5 (Paldea Evolved through 151)
# PPS5: SV04pt5-SV06pt5 (Paldean Fates through Shrouded Fable)
# PPS6: SV07 (Stellar Crown area)
# PPS7: SV08 (Surging Sparks area)
# PPS8: SV09-SV10 (Journey Together, Destined Rivals)

TOTAL_TO_PPS = {
    # PPS1 - SwSh era sets
    '202': 'PPS1',   # SWSH01 Sword & Shield (202 cards)
    '192': 'PPS1',   # SWSH02 Rebel Clash
    '189': 'PPS1',   # SWSH03 Darkness Ablaze
    '185': 'PPS1',   # SWSH04 Vivid Voltage
    '163': 'PPS1',   # SWSH05 Battle Styles / FST shard
    '203': 'PPS1',   # SWSH07 Evolving Skies
    '264': 'PPS1',   # SWSH08 Fusion Strike
    # PPS2 - SwSh late era
    '196': 'PPS2',   # SWSH10 Astral Radiance
    '195': 'PPS2',   # SWSH11 Lost Origin
    '182': 'PPS2',   # SWSH12 Silver Tempest
    # PPS3 - Transition SwSh->SV
    '172': 'PPS3',   # SWSH09 Brilliant Stars
    '198': 'PPS3',   # SV01 Scarlet & Violet
    # PPS4 - Early SV
    '193': 'PPS4',   # SV02 Paldea Evolved / SV04 Paradox Rift
    '197': 'PPS4',   # SV03 Obsidian Flames
    '191': 'PPS4',   # SV03pt5 151
    # PPS5 - Mid SV
    '162': 'PPS5',   # SV05 Temporal Forces
    '159': 'PPS5',   # SV06pt5 Shrouded Fable
    '064': 'PPS5',   # Shrouded Fable subset
    '167': 'PPS5',   # SV06 Twilight Masquerade
    # PPS6 - SV07
    '142': 'PPS6',   # SV07 Stellar Crown / SV10 Destined Rivals
    # PPS7 - SV08
    '132': 'PPS7',   # SV08 Surging Sparks subset
    '086': 'PPS7',   # small SV set
    # PPS8 - SV09-10
    '131': 'PPS8',   # SV09 Journey Together subset
    '165': 'PPS8',   # SV10 Destined Rivals subset
    '072': 'PPS8',
    '078': 'PPS8',
    '091': 'PPS8',
    '073': 'PPS8',
    '73':  'PPS8',
}

PPS_DEFS = {
    'PPS1': ('Prize Pack Series 1', '2022-11-09'),
    'PPS2': ('Prize Pack Series 2', '2023-01-19'),
    'PPS3': ('Prize Pack Series 3', '2023-08-14'),
    'PPS4': ('Prize Pack Series 4', '2024-02-14'),
    'PPS5': ('Prize Pack Series 5', '2024-08-01'),
    'PPS6': ('Prize Pack Series 6', '2024-11-01'),
    'PPS7': ('Prize Pack Series 7', '2025-02-01'),
    'PPS8': ('Prize Pack Series 8', '2025-08-01'),
}

sv_era = Era.objects.filter(code='B8').first()
pokemon_cat = Category.objects.filter(name='Pokemon').first()
orig_set = CardSet.objects.get(code='PRIZEPACK')

# Get/create PPS sets
pps_sets = {}
for code, (name, release) in PPS_DEFS.items():
    cs, created = CardSet.objects.get_or_create(
        code=code,
        defaults={'name': name, 'era': sv_era, 'release_date': release,
                  'symbol_url': orig_set.symbol_url or '',
                  'logo_url': orig_set.logo_url or '',
                  'regulation_mark': 'G'}
    )
    pps_sets[code] = cs
    print(f"  {'Created' if created else 'Exists'}: {code} - {name}")

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
}
VARIANT_MAP = {'Holofoil': 'H', 'Reverse Holofoil': 'RH', 'Normal': 'N', 'H': 'H', 'N': 'N', 'RH': 'RH'}

# Delete existing PRIZEPACK cards (not bundles)
all_codes = ['PRIZEPACK'] + list(PPS_DEFS.keys())
deleted = PokemonProduct.objects.filter(
    card_set__code__in=all_codes
).exclude(variant_override='BUNDLE').delete()
print(f"\nDeleted: {deleted[0]} cards")

# Read CSV and create fresh
print("Creating products from Bible CSV...")
created_count = 0
skipped = 0
unmatched_totals = set()

with open(CSV_PATH, encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) < 8 or row[2].strip() != 'PRIZEPACK':
            continue

        clean_name = (row[6].strip() or row[5].strip()).strip()
        card_num_raw = row[7].strip()
        rarity_raw = row[8].strip()
        variant_raw = row[24].strip() if len(row) > 24 else 'N'

        # Get total from card number
        card_total = ''
        card_num = None
        if '/' in card_num_raw:
            parts = card_num_raw.split('/')
            card_total = parts[1].strip()
            try:
                card_num = int(re.sub(r'[^0-9]', '', parts[0].strip()))
            except:
                pass
        else:
            try:
                card_num = int(re.sub(r'[^0-9]', '', card_num_raw))
            except:
                pass

        # Check series label in col 23 first
        series_label = row[23].strip() if len(row) > 23 else ''
        pps_code = None
        if series_label.startswith('Prize Pack Series'):
            m = re.search(r'Series (\d+)', series_label)
            if m:
                pps_code = f'PPS{m.group(1)}'

        # Fallback to total mapping
        if not pps_code:
            pps_code = TOTAL_TO_PPS.get(card_total)

        if not pps_code:
            unmatched_totals.add(card_total)
            pps_code = 'PRIZEPACK'  # keep in main set

        target_set = pps_sets.get(pps_code, orig_set)

        # Price
        def sf(v):
            try: return float(v.strip()) if v.strip() else None
            except: return None
        price = sf(row[15]) if len(row) > 15 else None
        if not price: price = sf(row[16]) if len(row) > 16 else None
        if not price: price = 0.00

        rarity = RARITY_MAP.get(rarity_raw, 'common')
        variant = VARIANT_MAP.get(variant_raw, 'N')
        pb_id = f"{target_set.code}-{card_num or 0}-{variant}"

        if PokemonProduct.objects.filter(pb_id=pb_id).exists():
            skipped += 1
            continue

        try:
            PokemonProduct.objects.create(
                pb_id=pb_id, name=clean_name, card_set=target_set,
                category=pokemon_cat, card_number=card_num,
                rarity=rarity, variant_override=variant,
                price=price, stock=0, is_active=True,
            )
            created_count += 1
        except Exception as e:
            print(f"  Error: {clean_name} — {e}")
            skipped += 1

print(f"\nCreated: {created_count} | Skipped: {skipped}")
if unmatched_totals:
    print(f"Unmatched totals (kept in PRIZEPACK): {sorted(unmatched_totals)}")
print("\nSummary:")
for code in ['PRIZEPACK'] + list(PPS_DEFS.keys()):
    cs = pps_sets.get(code, orig_set)
    count = PokemonProduct.objects.filter(card_set=cs).exclude(variant_override='BUNDLE').count()
    if count > 0:
        print(f"  {code}: {count} cards")
