"""
PokeBulk SA — TCGCSV Full Product Fetch
v1.0.0
Fetches ALL product data from TCGCSV for a given group ID
and saves raw JSON + flat CSV so you can decide what to use.

Save to: C:\Users\texca\pokemart-api\fetch_tcgcsv_all_v1.0.0.py

Usage:
    python fetch_tcgcsv_all_v1.0.0.py --group-id 604
    python fetch_tcgcsv_all_v1.0.0.py --group-id 604 --out-dir "D:\Claude Downloads\PokeBulk SA\Store Imports\Raw CSVs"
    python fetch_tcgcsv_all_v1.0.0.py --all-sets
"""

import csv
import json
import os
import sys
import time
import argparse
import urllib.request
from datetime import datetime

TCGCSV_BASE     = 'https://tcgcsv.com/tcgplayer/3/{group_id}/products'
PRICES_BASE     = 'https://tcgcsv.com/tcgplayer/3/{group_id}/prices'
SETS_URL        = 'https://tcgcsv.com/tcgplayer/3/groups'
DEFAULT_OUT_DIR = r'D:\Claude Downloads\PokeBulk SA\Store Imports\Raw CSVs'
DELAY_SECS      = 0.5


def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'PokeBulkSA-TCGCSVFetch/1.0.0'}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def flatten_product(product, prices_by_id):
    """Flatten a TCGCSV product record into a single dict with all fields."""
    row = {}

    # Core fields
    row['productId']     = product.get('productId', '')
    row['name']          = product.get('name', '')
    row['cleanName']     = product.get('cleanName', '')
    row['imageUrl']      = product.get('imageUrl', '')
    row['categoryId']    = product.get('categoryId', '')
    row['groupId']       = product.get('groupId', '')
    row['url']           = product.get('url', '')
    row['modifiedOn']    = product.get('modifiedOn', '')
    row['imageCount']    = product.get('imageCount', '')
    row['presaleInfo_isPresale']  = product.get('presaleInfo', {}).get('isPresale', '')
    row['presaleInfo_releasedOn'] = product.get('presaleInfo', {}).get('releasedOn', '')

    # Extended data — flatten all key/value pairs
    for item in product.get('extendedData', []):
        field_name = item.get('name', '').replace(' ', '_').replace('/', '_')
        row[f'ext_{field_name}'] = item.get('value', '')

    # Price data
    prices = prices_by_id.get(str(product.get('productId', '')), {})
    for sub_type, price_data in prices.items():
        prefix = f'price_{sub_type}'
        row[f'{prefix}_marketPrice']     = price_data.get('marketPrice', '')
        row[f'{prefix}_lowPrice']        = price_data.get('lowPrice', '')
        row[f'{prefix}_midPrice']        = price_data.get('midPrice', '')
        row[f'{prefix}_highPrice']       = price_data.get('highPrice', '')
        row[f'{prefix}_directLowPrice']  = price_data.get('directLowPrice', '')
        row[f'{prefix}_subTypeName']     = price_data.get('subTypeName', '')

    return row


def fetch_prices(group_id):
    """Fetch all prices for a group, return dict keyed by productId."""
    url = PRICES_BASE.format(group_id=group_id)
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
        print(f'  WARNING: Could not fetch prices: {e}')
        return {}


def fetch_group(group_id, out_dir):
    """Fetch all products for a group and save to JSON + CSV."""
    os.makedirs(out_dir, exist_ok=True)

    print(f'\n📦 Fetching group {group_id}...')

    # Fetch products
    url = TCGCSV_BASE.format(group_id=group_id)
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f'  ERROR: {e}')
        return 0

    results = data.get('results', [])
    print(f'  {len(results)} products found')

    if not results:
        return 0

    # Fetch prices
    print(f'  Fetching prices...')
    prices_by_id = fetch_prices(group_id)
    time.sleep(DELAY_SECS)

    # Save raw JSON
    json_path = os.path.join(out_dir, f'tcgcsv_{group_id}_raw.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f'  Saved raw JSON: {json_path}')

    # Flatten all products
    rows = [flatten_product(p, prices_by_id) for p in results]

    # Collect all column names
    all_cols = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                all_cols.append(k)
                seen.add(k)

    # Save flat CSV
    csv_path = os.path.join(out_dir, f'tcgcsv_{group_id}_flat.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=all_cols, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print(f'  Saved flat CSV : {csv_path}')
    print(f'  Columns        : {len(all_cols)}')

    return len(results)


def fetch_all_sets(out_dir):
    """Fetch the full set list from TCGCSV and process each group."""
    print('Fetching all Pokemon sets from TCGCSV...')
    try:
        data = fetch_json(SETS_URL)
    except Exception as e:
        print(f'ERROR fetching sets: {e}')
        return

    results = data.get('results', [])
    print(f'Found {len(results)} groups\n')

    # Save sets list
    os.makedirs(out_dir, exist_ok=True)
    sets_path = os.path.join(out_dir, 'tcgcsv_all_groups.json')
    with open(sets_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    # Also save as CSV
    sets_csv_path = os.path.join(out_dir, 'tcgcsv_all_groups.csv')
    if results:
        cols = list(results[0].keys())
        with open(sets_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
    print(f'Saved groups list: {sets_csv_path}')

    total = 0
    for i, group in enumerate(results):
        group_id   = group.get('groupId')
        group_name = group.get('name', '')
        print(f'\n[{i+1}/{len(results)}] {group_name} (ID: {group_id})')
        count = fetch_group(group_id, out_dir)
        total += count
        time.sleep(DELAY_SECS)

    print(f'\n✅ Done! Total products fetched: {total}')


def main():
    parser = argparse.ArgumentParser(
        description='PokeBulk SA - TCGCSV Full Product Fetch v1.0.0'
    )
    parser.add_argument('--group-id', type=int, help='Fetch single group by ID')
    parser.add_argument('--all-sets', action='store_true', help='Fetch ALL sets')
    parser.add_argument(
        '--out-dir',
        type=str,
        default=DEFAULT_OUT_DIR,
        help='Output directory for JSON and CSV files'
    )
    args = parser.parse_args()

    if not args.group_id and not args.all_sets:
        print('Usage:')
        print('  python fetch_tcgcsv_all_v1.0.0.py --group-id 604')
        print('  python fetch_tcgcsv_all_v1.0.0.py --all-sets')
        sys.exit(1)

    print('=' * 60)
    print('PokeBulk SA - TCGCSV Full Product Fetch v1.0.0')
    print(f'Output dir: {args.out_dir}')
    print(f'Timestamp : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    if args.all_sets:
        fetch_all_sets(args.out_dir)
    else:
        fetch_group(args.group_id, args.out_dir)


if __name__ == '__main__':
    main()
