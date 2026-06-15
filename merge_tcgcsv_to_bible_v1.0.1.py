# PokeBulk SA - Merge TCGCSV Downloads into Bible
# v1.0.1
# Matches on product_id + variant_code
# TCGCSV data supersedes bible where available
# Adds new rows for products/variants not in bible
#
# Save to: C:\Users\texca\pokemart-api\merge_tcgcsv_to_bible_v1.0.1.py
#
# Usage:
#   python merge_tcgcsv_to_bible_v1.0.1.py --dry-run
#   python merge_tcgcsv_to_bible_v1.0.1.py

import csv
import os
import sys
import glob
import argparse
from datetime import datetime

DEFAULT_BIBLE    = os.path.join('C:\\', 'Users', 'texca', 'pokemart-api', 'pokebulk_bible_v5.csv')
DEFAULT_TCGCSV   = os.path.join('D:\\', 'Claude Downloads', 'PokeBulk SA', 'Store Imports', 'Raw CSVs')
DEFAULT_OUT      = os.path.join('C:\\', 'Users', 'texca', 'pokemart-api', 'pokebulk_bible_v6.csv')

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

PRICE_FIELDS = {
    'H':  ('price_Holofoil_market',         'price_Holofoil_low',         'price_Holofoil_mid',         'price_Holofoil_high'),
    'N':  ('price_Normal_market',           'price_Normal_low',           'price_Normal_mid',           'price_Normal_high'),
    'RH': ('price_Reverse_Holofoil_market', 'price_Reverse_Holofoil_low', 'price_Reverse_Holofoil_mid', 'price_Reverse_Holofoil_high'),
}

CARD_DATA_FIELDS = {
    'card_text':    'ext_CardText',
    'attack_1':     'ext_Attack_1',
    'attack_2':     'ext_Attack_2',
    'weakness':     'ext_Weakness',
    'resistance':   'ext_Resistance',
    'retreat_cost': 'ext_RetreatCost',
    'hp':           'ext_HP',
    'stage':        'ext_Stage',
    'card_type':    'ext_Card_Type',
}


def load_tcgcsv(tcgcsv_dir):
    print('Loading TCGCSV flat files...')
    products = {}
    files = glob.glob(os.path.join(tcgcsv_dir, '*_flat.csv'))
    print('  Found ' + str(len(files)) + ' flat CSV files')
    for filepath in files:
        try:
            with open(filepath, newline='', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    pid = str(row.get('productId', '')).strip()
                    if pid:
                        products[pid] = row
        except Exception as e:
            print('  WARNING: ' + filepath + ': ' + str(e))
    print('  Loaded ' + str(len(products)) + ' unique products\n')
    return products


def get_prices(tcgcsv_row, variant_code):
    cols = PRICE_FIELDS.get(variant_code, PRICE_FIELDS['N'])
    return (
        tcgcsv_row.get(cols[0], ''),
        tcgcsv_row.get(cols[1], ''),
        tcgcsv_row.get(cols[2], ''),
        tcgcsv_row.get(cols[3], ''),
    )


def merge(bible_path, tcgcsv_dir, out_path, dry_run):
    print('=' * 60)
    print('PokeBulk SA - Merge TCGCSV to Bible v1.0.1')
    print('Bible   : ' + bible_path)
    print('TCGCSV  : ' + tcgcsv_dir)
    print('Output  : ' + out_path)
    print('Dry run : ' + str(dry_run))
    print('=' * 60 + '\n')

    tcgcsv = load_tcgcsv(tcgcsv_dir)

    print('Loading bible...')
    bible_rows = []
    bible_cols = []
    with open(bible_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        bible_cols = reader.fieldnames[:]
        for row in reader:
            bible_rows.append(row)
    print('  ' + str(len(bible_rows)) + ' rows, ' + str(len(bible_cols)) + ' columns\n')

    bible_lookup = {}
    for i, row in enumerate(bible_rows):
        pid = str(row.get('product_id', '')).strip()
        if pid:
            if pid not in bible_lookup:
                bible_lookup[pid] = []
            bible_lookup[pid].append(i)

    updated = unchanged = new_rows = not_found = 0
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print('Updating existing bible rows...')
    for pid, indices in bible_lookup.items():
        tcgcsv_row = tcgcsv.get(pid)
        if not tcgcsv_row:
            not_found += 1
            continue

        for idx in indices:
            row = bible_rows[idx]
            variant_code = row.get('variant_code', 'N').strip() or 'N'
            changed = False

            # Update prices for this variant
            market, low, mid, high = get_prices(tcgcsv_row, variant_code)
            for field, val in [('market_usd', market), ('low_usd', low), ('mid_usd', mid), ('high_usd', high)]:
                if val and row.get(field, '') != val:
                    row[field] = val
                    changed = True

            # Always update image URL and modified date
            img = tcgcsv_row.get('imageUrl', '').strip()
            if img and row.get('tcgplayer_image_url', '') != img:
                row['tcgplayer_image_url'] = img
                changed = True

            mod = tcgcsv_row.get('modifiedOn', '').strip()
            if mod:
                row['tcgplayer_modified'] = mod
                changed = True

            # Fill empty card data fields
            for bible_field, tcgcsv_field in CARD_DATA_FIELDS.items():
                val = tcgcsv_row.get(tcgcsv_field, '').strip()
                if val and not row.get(bible_field, '').strip():
                    row[bible_field] = val
                    changed = True

            if changed:
                row['bible_built_at'] = now
                updated += 1
            else:
                unchanged += 1

    print('Checking for new products...')
    for pid, tcgcsv_row in tcgcsv.items():
        if pid in bible_lookup:
            continue

        variants_found = []
        for sub, code in SUBTYPE_MAP.items():
            if not sub:
                continue
            safe = sub.replace(' ', '_')
            if tcgcsv_row.get('price_' + safe + '_market', '').strip():
                if code not in [v[0] for v in variants_found]:
                    variants_found.append((code, sub))

        if not variants_found:
            variants_found = [('H', 'Holofoil')]

        for variant_code, sub_type in variants_found:
            market, low, mid, high = get_prices(tcgcsv_row, variant_code)
            new_row = {col: '' for col in bible_cols}
            new_row['product_id']          = pid
            new_row['name']                = tcgcsv_row.get('name', '')
            new_row['clean_name']          = tcgcsv_row.get('cleanName', '')
            new_row['number']              = tcgcsv_row.get('ext_Number', '')
            new_row['card_number']         = tcgcsv_row.get('ext_Number', '').split('/')[0].strip()
            new_row['rarity']              = tcgcsv_row.get('ext_Rarity', '')
            new_row['card_type']           = tcgcsv_row.get('ext_Card_Type', '')
            new_row['hp']                  = tcgcsv_row.get('ext_HP', '')
            new_row['stage']               = tcgcsv_row.get('ext_Stage', '')
            new_row['card_text']           = tcgcsv_row.get('ext_CardText', '')
            new_row['attack_1']            = tcgcsv_row.get('ext_Attack_1', '')
            new_row['attack_2']            = tcgcsv_row.get('ext_Attack_2', '')
            new_row['weakness']            = tcgcsv_row.get('ext_Weakness', '')
            new_row['resistance']          = tcgcsv_row.get('ext_Resistance', '')
            new_row['retreat_cost']        = tcgcsv_row.get('ext_RetreatCost', '')
            new_row['variant_code']        = variant_code
            new_row['variant']             = sub_type
            new_row['market_usd']          = market
            new_row['low_usd']             = low
            new_row['mid_usd']             = mid
            new_row['high_usd']            = high
            new_row['tcgplayer_image_url'] = tcgcsv_row.get('imageUrl', '')
            new_row['tcgplayer_url']       = tcgcsv_row.get('url', '')
            new_row['tcgplayer_modified']  = tcgcsv_row.get('modifiedOn', '')
            new_row['tcgcsv_group_id']     = str(tcgcsv_row.get('groupId', ''))
            new_row['is_card']             = '1'
            new_row['bible_built_at']      = now
            bible_rows.append(new_row)
            new_rows += 1

    print('\n' + '=' * 60)
    print('DRY RUN - no changes saved' if dry_run else 'Writing output...')
    print('  Updated       : ' + str(updated))
    print('  Unchanged     : ' + str(unchanged))
    print('  New rows      : ' + str(new_rows))
    print('  Not in TCGCSV : ' + str(not_found))
    print('  Total output  : ' + str(len(bible_rows)))

    if not dry_run:
        with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=bible_cols, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(bible_rows)
        print('  Saved: ' + out_path)

    print('=' * 60)


def main():
    parser = argparse.ArgumentParser(description='PokeBulk SA - Merge TCGCSV to Bible v1.0.1')
    parser.add_argument('--dry-run',    action='store_true')
    parser.add_argument('--bible',      type=str, default=DEFAULT_BIBLE)
    parser.add_argument('--tcgcsv-dir', type=str, default=DEFAULT_TCGCSV)
    parser.add_argument('--out',        type=str, default=DEFAULT_OUT)
    args = parser.parse_args()
    merge(args.bible, args.tcgcsv_dir, args.out, args.dry_run)


if __name__ == '__main__':
    main()
