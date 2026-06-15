# PokeBulk SA - TCGCSV Full Product Fetch
# v1.0.1
# Fetches ALL product data from TCGCSV including prices
# Saves raw JSON + flat CSV per set
#
# Save to: C:\Users\texca\pokemart-api\fetch_tcgcsv_all_v1.0.1.py
#
# Usage:
#   python fetch_tcgcsv_all_v1.0.1.py --group-id 604
#   python fetch_tcgcsv_all_v1.0.1.py --all-sets
#   python fetch_tcgcsv_all_v1.0.1.py --group-id 604 --out-dir "C:\MyFolder"

import csv
import json
import os
import sys
import time
import argparse
import urllib.request
from datetime import datetime

TCGCSV_PRODUCTS = 'https://tcgcsv.com/tcgplayer/3/{group_id}/products'
TCGCSV_PRICES   = 'https://tcgcsv.com/tcgplayer/3/{group_id}/prices'
TCGCSV_GROUPS   = 'https://tcgcsv.com/tcgplayer/3/groups'
DEFAULT_OUT_DIR  = os.path.join('D:\\', 'Claude Downloads', 'PokeBulk SA', 'Store Imports', 'Raw CSVs')
DELAY_SECS       = 0.5


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'PokeBulkSA-TCGCSVFetch/1.0.1'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def fetch_prices(group_id):
    url = TCGCSV_PRICES.format(group_id=group_id)
    try:
        data = fetch_json(url)
        prices = {}
        for item in data.get('results', []):
            pid = str(item.get('productId', ''))
            sub = item.get('subTypeName', 'Normal')
            if pid not in prices:
                prices[pid] = {}
            prices[pid][sub] = item
        return prices
    except Exception as e:
        print('  WARNING: Could not fetch prices: ' + str(e))
        return {}


def flatten_product(product, prices_by_id):
    row = {}

    # Core fields
    row['productId']              = product.get('productId', '')
    row['name']                   = product.get('name', '')
    row['cleanName']              = product.get('cleanName', '')
    row['imageUrl']               = product.get('imageUrl', '')
    row['categoryId']             = product.get('categoryId', '')
    row['groupId']                = product.get('groupId', '')
    row['url']                    = product.get('url', '')
    row['modifiedOn']             = product.get('modifiedOn', '')
    row['imageCount']             = product.get('imageCount', '')
    row['presale_isPresale']      = product.get('presaleInfo', {}).get('isPresale', '')
    row['presale_releasedOn']     = product.get('presaleInfo', {}).get('releasedOn', '')

    # Extended data - all fields
    ext_fields = [
        'Number', 'Rarity', 'Card Type', 'HP', 'Stage',
        'CardText', 'Attack 1', 'Attack 2', 'Attack 3',
        'Weakness', 'Resistance', 'RetreatCost',
        'Ability', 'AncientTrait', 'FlavorText',
        'Artist', 'Regulation Mark', 'Rules',
    ]
    # First add known fields in order
    known = {item['name']: item.get('value', '') for item in product.get('extendedData', [])}
    for field in ext_fields:
        col = 'ext_' + field.replace(' ', '_')
        row[col] = known.get(field, '')
    # Then add any extra fields not in our list
    for item in product.get('extendedData', []):
        col = 'ext_' + item['name'].replace(' ', '_')
        if col not in row:
            row[col] = item.get('value', '')

    # Price data - all sub-types
    pid = str(product.get('productId', ''))
    price_subtypes = prices_by_id.get(pid, {})
    for sub_type, price_data in price_subtypes.items():
        safe = sub_type.replace(' ', '_')
        row['price_' + safe + '_market']      = price_data.get('marketPrice', '')
        row['price_' + safe + '_low']         = price_data.get('lowPrice', '')
        row['price_' + safe + '_mid']         = price_data.get('midPrice', '')
        row['price_' + safe + '_high']        = price_data.get('highPrice', '')
        row['price_' + safe + '_directLow']   = price_data.get('directLowPrice', '')

    return row


def fetch_group(group_id, out_dir, group_name=''):
    os.makedirs(out_dir, exist_ok=True)
    label = group_name or str(group_id)
    print('  Fetching products...')

    try:
        data = fetch_json(TCGCSV_PRODUCTS.format(group_id=group_id))
    except Exception as e:
        print('  ERROR: ' + str(e))
        return 0

    results = data.get('results', [])
    print('  ' + str(len(results)) + ' products found')

    if not results:
        return 0

    # Fetch prices
    print('  Fetching prices...')
    prices_by_id = fetch_prices(group_id)
    time.sleep(DELAY_SECS)

    # Save raw JSON
    json_path = os.path.join(out_dir, 'tcgcsv_' + str(group_id) + '_raw.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    # Flatten all products
    rows = [flatten_product(p, prices_by_id) for p in results]

    # Collect all columns in order
    all_cols = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                all_cols.append(k)
                seen.add(k)

    # Save flat CSV
    csv_path = os.path.join(out_dir, 'tcgcsv_' + str(group_id) + '_flat.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=all_cols, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print('  Saved: ' + csv_path)
    print('  Columns: ' + str(len(all_cols)))
    return len(results)


def fetch_all_sets(out_dir):
    print('Fetching all Pokemon groups from TCGCSV...')
    try:
        data = fetch_json(TCGCSV_GROUPS)
    except Exception as e:
        print('ERROR: ' + str(e))
        return

    results = data.get('results', [])
    print('Found ' + str(len(results)) + ' groups\n')

    os.makedirs(out_dir, exist_ok=True)

    # Save groups list as CSV
    if results:
        groups_csv = os.path.join(out_dir, 'tcgcsv_all_groups.csv')
        cols = list(results[0].keys())
        with open(groups_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
        print('Saved groups list: ' + groups_csv + '\n')

    total = 0
    for i, group in enumerate(results):
        group_id   = group.get('groupId')
        group_name = group.get('name', '')
        print('[' + str(i+1) + '/' + str(len(results)) + '] ' + group_name + ' (ID: ' + str(group_id) + ')')
        count = fetch_group(group_id, out_dir, group_name)
        total += count
        time.sleep(DELAY_SECS)

    print('\n' + '=' * 50)
    print('Done! Total products fetched: ' + str(total))
    print('=' * 50)


def main():
    parser = argparse.ArgumentParser(description='PokeBulk SA - TCGCSV Full Product Fetch v1.0.1')
    parser.add_argument('--group-id', type=int, help='Fetch single group by TCGCSV group ID')
    parser.add_argument('--all-sets', action='store_true', help='Fetch ALL sets from TCGCSV')
    parser.add_argument('--out-dir', type=str, default=DEFAULT_OUT_DIR, help='Output directory')
    args = parser.parse_args()

    if not args.group_id and not args.all_sets:
        print('Usage:')
        print('  python fetch_tcgcsv_all_v1.0.1.py --group-id 604')
        print('  python fetch_tcgcsv_all_v1.0.1.py --all-sets')
        sys.exit(1)

    print('=' * 50)
    print('PokeBulk SA - TCGCSV Full Product Fetch v1.0.1')
    print('Output dir: ' + args.out_dir)
    print('Timestamp : ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('=' * 50 + '\n')

    if args.all_sets:
        fetch_all_sets(args.out_dir)
    else:
        fetch_group(args.group_id, args.out_dir)
        print('Done!')


if __name__ == '__main__':
    main()
