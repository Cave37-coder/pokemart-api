# PokeBulk SA - Merge TCGCSV Downloads into Bible
# v1.0.0
# Matches on product_id + variant_code
# TCGCSV data supersedes bible where available
# Adds new rows for products/variants not in bible
#
# Save to: C:\Users\texca\pokemart-api\merge_tcgcsv_to_bible_v1.0.0.py
#
# Usage:
#   python merge_tcgcsv_to_bible_v1.0.0.py --dry-run
#   python merge_tcgcsv_to_bible_v1.0.0.py

import csv
import os
import sys
import glob
import argparse
from datetime import datetime

BIBLE_PATH   = os.path.join('C:\\', 'Users', 'texca', 'pokemart-api', 'pokebulk_bible_v5.csv')
TCGCSV_DIR   = os.path.join('D:\\', 'Claude Downloads', 'PokeBulk SA', 'Store Imports', 'Raw CSVs')
OUT_PATH     = os.path.join('C:\\', 'Users', 'texca', 'pokemart-api', 'pokebulk_bible_v6.csv')

# Variant mapping from TCGCSV subTypeName to variant_code
SUBTYPE_MAP = {
    'Normal':               'N',
    'Holofoil':             'H',
    'Reverse Holofoil':     'RH',
    '1st Edition Normal':   'N',
    '1st Edition Holofoil': 'H',
    'Unlimited Normal':     'N',
    'Unlimited Holofoil':   'H',
    '1st Edition':          'N',
    'Unlimited':            'N',
    '':                     'H',
}

# Bible fields to update from TCGCSV flat CSV
# bible_field: tcgcsv_flat_field
UPDATE_FIELDS = {
    'market_usd':         'price_Normal_market',
    'low_usd':            'price_Normal_low',
    'mid_usd':            'price_Normal_mid',
    'high_usd':           'price_Normal_high',
    'tcgplayer_image_url':'imageUrl',
    'tcgplayer_modified': 'modifiedOn',
    'card_text':          'ext_CardText',
    'attack_1':           'ext_Attack_1',
    'attack_2':           'ext_Attack_2',
    'weakness':           'ext_Weakness',
    'resistance':         'ext_Resistance',
    'retreat_cost':       'ext_RetreatCost',
    'hp':                 'ext_HP',
    'stage':              'ext_Stage',
    'card_type':          'ext_Card_Type',
}

# Price fields per variant subtype
PRICE_FIELDS = {
    'H':  ('price_Holofoil_market', 'price_Holofoil_low', 'price_Holofoil_mid', 'price_Holofoil_high'),
    'N':  ('price_Normal_market',   'price_Normal_low',   'price_Normal_mid',   'price_Normal_high'),
    'RH': ('price_Reverse_Holofoil_market', 'price_Reverse_Holofoil_low', 'price_Reverse_Holofoil_mid', 'price_Reverse_Holofoil_high'),
}


def load_tcgcsv_flat_files(tcgcsv_dir):
    print('Loading TCGCSV flat files...')
    # Dict: product_id -> flat row
    products = {}
    files = glob.glob(os.path.join(tcgcsv_dir, '*_flat.csv'))
    print('  Found ' + str(len(files)) + ' flat CSV files')

    for filepath in files:
        try:
            with open(filepath, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid = str(row.get('productId', '')).strip()
                    if pid:
                        products[pid] = row
        except Exception as e:
            print('  WARNING: Could not read ' + filepath + ': ' + str(e))

    print('  Loaded ' + str(len(products)) + ' unique products from TCGCSV\n')
    return products


def get_price_for_variant(tcgcsv_row, variant_code):
    price_cols = PRICE_FIELDS.get(variant_code, PRICE_FIELDS['N'])
    market = tcgcsv_row.get(price_cols[0], '')
    low    = tcgcsv_row.get(price_cols[1], '')
    mid    = tcgcsv_row.get(price_cols[2], '')
    high   = tcgcsv_row.get(price_cols[3], '')
    return market, low, mid, high


def merge(dry_run):
    print('=' * 60)
    print('PokeBulk SA - Merge TCGCSV to Bible v1.0.0')
    print('Bible   : ' + BIBLE_PATH)
    print('TCGCSV  : ' + TCGCSV_DIR)
    print('Output  : ' + OUT_PATH)
    print('Dry run : ' + str(dry_run))
    print('=' * 60 + '\n')

    # Load TCGCSV flat files
    tcgcsv = load_tcgcsv_flat_files(TCGCSV_DIR)

    # Load existing bible
    print('Loading bible...')
    bible_rows = []
    bible_cols = []
    with open(BIBLE_PATH, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        bible_cols = reader.fieldnames[:]
        for row in reader:
            bible_rows.append(row)
    print('  ' + str(len(bible_rows)) + ' rows, ' + str(len(bible_cols)) + ' columns\n')

    # Build lookup: product_id -> list of bible row indices (one per variant)
    bible_lookup = {}
    for i, row in enumerate(bible_rows):
        pid = str(row.get('product_id', '')).strip()
        if pid:
            if pid not in bible_lookup:
                bible_lookup[pid] = []
            bible_lookup[pid].append(i)

    # Track stats
    updated   = 0
    new_rows  = 0
    unchanged = 0
    not_found = 0

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Update existing bible rows from TCGCSV
    print('Updating existing bible rows...')
    for pid, indices in bible_lookup.items():
        tcgcsv_row = tcgcsv.get(pid)
        if not tcgcsv_row:
            not_found += 1
            continue

        for idx in indices:
            row = bible_rows[idx]
            variant_code = row.get('variant_code', 'N').strip()
            changed = False

            # Get prices for this variant
            market, low, mid, high = get_price_for_variant(tcgcsv_row, variant_code)

            # Update price fields
            if market and row.get('market_usd', '') != market:
                row['market_usd'] = market
                changed = True
            if low and row.get('low_usd', '') != low:
                row['low_usd'] = low
                changed = True
            if mid and row.get('mid_usd', '') != mid:
                row['mid_usd'] = mid
                changed = True
            if high and row.get('high_usd', '') != high:
                row['high_usd'] = high
                changed = True

            # Update card data fields (only if empty in bible)
            for bible_field, tcgcsv_field in UPDATE_FIELDS.items():
                if bible_field in ('market_usd','low_usd','mid_usd','high_usd'):
                    continue  # already handled above
                tcgcsv_val = tcgcsv_row.get(tcgcsv_field, '').strip()
                bible_val  = row.get(bible_field, '').strip()
                if tcgcsv_val and not bible_val:
                    row[bible_field] = tcgcsv_val
                    changed = True
                elif bible_field == 'tcgplayer_image_url' and tcgcsv_val:
                    # Always update image URL
                    row[bible_field] = tcgcsv_val
                    changed = True
                elif bible_field == 'tcgplayer_modified' and tcgcsv_val:
                    row[bible_field] = tcgcsv_val
                    changed = True

            if changed:
                row['bible_built_at'] = now
                updated += 1
            else:
                unchanged += 1

    # Find new products not in bible
    print('Checking for new products...')
    new_product_rows = []
    for pid, tcgcsv_row in tcgcsv.items():
        if pid in bible_lookup:
            continue

        # This product is not in bible at all — add it
        # Determine variants from price columns
        variants_found = []
        for sub, code in SUBTYPE_MAP.items():
            if not sub:
                continue
            safe_sub = sub.replace(' ', '_')
            market_col = 'price_' + safe_sub + '_market'
            if tcgcsv_row.get(market_col, '').strip():
                if code not in [v[0] for v in variants_found]:
                    variants_found.append((code, sub))

        # Default to H if no prices found (single card)
        if not variants_found:
            variants_found = [('H', 'Holofoil')]

        group_id = str(tcgcsv_row.get('groupId', '')).strip()

        for variant_code, sub_type in variants_found:
            market, low, mid, high = get_price_for_variant(tcgcsv_row, variant_code)
            new_row = {col: '' for col in bible_cols}
            new_row['product_id']         = pid
            new_row['name']               = tcgcsv_row.get('name', '')
            new_row['clean_name']         = tcgcsv_row.get('cleanName', '')
            new_row['number']             = tcgcsv_row.get('ext_Number', '')
            new_row['card_number']        = tcgcsv_row.get('ext_Number', '').split('/')[0].strip()
            new_row['rarity']             = tcgcsv_row.get('ext_Rarity', '')
            new_row['card_type']          = tcgcsv_row.get('ext_Card_Type', '')
            new_row['hp']                 = tcgcsv_row.get('ext_HP', '')
            new_row['stage']              = tcgcsv_row.get('ext_Stage', '')
            new_row['card_text']          = tcgcsv_row.get('ext_CardText', '')
            new_row['attack_1']           = tcgcsv_row.get('ext_Attack_1', '')
            new_row['attack_2']           = tcgcsv_row.get('ext_Attack_2', '')
            new_row['weakness']           = tcgcsv_row.get('ext_Weakness', '')
            new_row['resistance']         = tcgcsv_row.get('ext_Resistance', '')
            new_row['retreat_cost']       = tcgcsv_row.get('ext_RetreatCost', '')
            new_row['variant_code']       = variant_code
            new_row['variant']            = sub_type
            new_row['market_usd']         = market
            new_row['low_usd']            = low
            new_row['mid_usd']            = mid
            new_row['high_usd']           = high
            new_row['tcgplayer_image_url']= tcgcsv_row.get('imageUrl', '')
            new_row['tcgplayer_url']      = tcgcsv_row.get('url', '')
            new_row['tcgplayer_modified'] = tcgcsv_row.get('modifiedOn', '')
            new_row['tcgcsv_group_id']    = group_id
            new_row['is_card']            = '1'
            new_row['bible_built_at']     = now
            new_product_rows.append(new_row)
            new_rows += 1

    print('\n' + '=' * 60)
    print('DRY RUN - no changes saved' if dry_run else 'Writing output...')
    print('  Updated   : ' + str(updated))
    print('  Unchanged : ' + str(unchanged))
    print('  New rows  : ' + str(new_rows))
    print('  Not in TCGCSV: ' + str(not_found))
    print('  Total output rows: ' + str(len(bible_rows) + len(new_product_rows)))

    if not dry_run:
        with open(OUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=bible_cols, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(bible_rows)
            writer.writerows(new_product_rows)
        print('  Saved to: ' + OUT_PATH)

    print('=' * 60)


def main():
    parser = argparse.ArgumentParser(description='PokeBulk SA - Merge TCGCSV to Bible v1.0.0')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
    parser.add_argument('--bible', type=str, default=BIBLE_PATH)
    parser.add_argument('--tcgcsv-dir', type=str, default=TCGCSV_DIR)
    parser.add_argument('--out', type=str, default=OUT_PATH)
    args = parser.parse_args()

    global BIBLE_PATH, TCGCSV_DIR, OUT_PATH
    BIBLE_PATH  = args.bible
    TCGCSV_DIR  = args.tcgcsv_dir
    OUT_PATH    = args.out

    merge(args.dry_run)


if __name__ == '__main__':
    main()
