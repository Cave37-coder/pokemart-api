# PokeBulk SA - Fetch Single Set Into Bible-Format Sheet
# v1.0
#
# Fetches one TCGCSV group (default: Pitch Black / ME05, group_id 24688) and
# reshapes it into the EXACT column structure of pokebulk_bible_v6.csv, so you
# get a standalone check sheet before anything is merged into the real bible.
#
# This is a CHECK SHEET ONLY. It populates the columns TCGCSV actually
# provides and leaves everything else blank -- exactly matching pipeline
# order (TCGCSV master -> Bulbapedia enrich -> pokemontcg.io fallback ->
# pricing markup). No pricing markup (pokebulk_zar / usd_zar_rate), no
# Bulbapedia enrichment, no legality data -- those come from later steps
# you already have scripts for.
#
# Save to: C:\Users\texca\pokemart-api\fetch_set_bible_format_v1.0.py
#
# Usage:
#   python fetch_set_bible_format_v1.0.py
#   python fetch_set_bible_format_v1.0.py --group-id 24688 --set-code PBL --era "Mega Evolution"
#   python fetch_set_bible_format_v1.0.py --group-id 604 --set-code BS --era "WotC Base" --out-dir "C:\MyFolder"

import csv
import json
import os
import sys
import time
import argparse
import urllib.request
from datetime import datetime

TCGCSV_PRODUCTS = 'https://tcgcsv.com/tcgplayer/3/{group_id}/products'
TCGCSV_PRICES = 'https://tcgcsv.com/tcgplayer/3/{group_id}/prices'
TCGCSV_GROUPS = 'https://tcgcsv.com/tcgplayer/3/groups'
DEFAULT_OUT_DIR = os.path.join('D:\\', 'Claude Downloads', 'PokeBulk SA', 'Store Imports', 'Check Sheets')
DELAY_SECS = 0.5

# Exact 70-column bible schema, in order, from pokebulk_bible_v6.csv
BIBLE_COLUMNS = [
    'group_id', 'set_code', 'era', 'set_name', 'tcgcsv_group_id', 'ptcgio_set_id',
    'bulba_set_page', 'product_id', 'name', 'clean_name', 'number', 'card_number',
    'rarity', 'card_type', 'hp', 'stage', 'card_text', 'attack_1', 'attack_2',
    'weakness', 'resistance', 'retreat_cost', 'variant', 'variant_code', 'is_card',
    'is_stamped', 'stamp_type', 'market_usd', 'low_usd', 'mid_usd', 'high_usd',
    'pokebulk_zar', 'usd_zar_rate', 'tcgplayer_image_url', 'tcgplayer_url',
    'bulbapedia_image_url', 'ptcg_image_url', 'final_image_url', 'artist',
    'pokedex_numbers', 'regulation_mark', 'legality_standard', 'legality_expanded',
    'legality_unlimited', 'tcgplayer_modified', 'bible_built_at', 'bulba_page_title',
    'bulba_image_filename', 'bulba_image_url', 'bulba_artist', 'bulba_pokedex_number',
    'bulba_regulation_mark', 'bulba_legality_standard', 'bulba_legality_expanded',
    'bulba_legality_unlimited', 'bulba_matched', 'bulba_match_method',
    'bulba_enriched_at', 'ptcg_set_id', 'ptcg_card_id', 'ptcg_image_small',
    'ptcg_image_large', 'ptcg_artist', 'ptcg_regulation_mark', 'ptcg_pokedex',
    'ptcg_matched', 'final_image_source', 'final_artist', 'final_pokedex',
    'final_regulation_mark',
]

# Known TCGCSV subTypeName -> your VALID_VARIANTS code (from products/views.py).
# Anything not in this dict gets flagged at the end for you to review/extend --
# ball variants (PB/MB/LB/etc.) and other special codes aren't reliably labeled
# by TCGCSV itself and usually need Bulbapedia/manual confirmation.
VARIANT_CODE_MAP = {
    'Normal': 'N',
    'Holofoil': 'H',
    'Reverse Holofoil': 'RH',
    '1st Edition Normal': 'N',
    '1st Edition Holofoil': 'H',
}


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'PokeBulkSA-BibleFormatFetch/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_group_name(group_id):
    """Best-effort lookup of the TCGCSV group name, for logging only."""
    try:
        data = fetch_json(TCGCSV_GROUPS)
        for g in data.get('results', []):
            if g.get('groupId') == group_id:
                return g.get('name', ''), g.get('abbreviation', '')
    except Exception as e:
        print('  (could not look up group name: ' + str(e) + ')')
    return '', ''


def fetch_prices(group_id):
    url = TCGCSV_PRICES.format(group_id=group_id)
    try:
        data = fetch_json(url)
        prices = {}
        for item in data.get('results', []):
            pid = str(item.get('productId', ''))
            sub = item.get('subTypeName', 'Normal')
            prices.setdefault(pid, {})[sub] = item
        return prices
    except Exception as e:
        print('  WARNING: Could not fetch prices: ' + str(e))
        return {}


def parse_card_number(number_str):
    """'005/086' -> 5.0 ; '' or unparsable -> ''"""
    if not number_str:
        return ''
    prefix = number_str.split('/')[0].strip()
    try:
        return float(int(prefix))
    except ValueError:
        return ''


def build_rows(product, prices_by_id, set_code, era, set_name, group_id, unmapped_variants):
    ext = {item['name']: item.get('value', '') for item in product.get('extendedData', [])}
    is_card = bool(ext.get('Rarity') or ext.get('Number'))

    pid = str(product.get('productId', ''))
    price_subtypes = prices_by_id.get(pid, {})
    # If a product has no price data at all yet (common for very new/prerelease
    # sets), still emit one row so it shows up in the check sheet.
    subtype_names = list(price_subtypes.keys()) or ['Normal']

    rows = []
    for sub in subtype_names:
        price_data = price_subtypes.get(sub, {})
        variant_code = VARIANT_CODE_MAP.get(sub, '')
        if variant_code == '' and sub not in unmapped_variants:
            unmapped_variants.add(sub)

        row = {col: '' for col in BIBLE_COLUMNS}
        row.update({
            'group_id': group_id,
            'set_code': set_code,
            'era': era,
            'set_name': set_name,
            'tcgcsv_group_id': group_id,
            'product_id': product.get('productId', ''),
            'name': product.get('name', ''),
            'clean_name': product.get('cleanName', ''),
            'number': ext.get('Number', ''),
            'card_number': parse_card_number(ext.get('Number', '')),
            'rarity': ext.get('Rarity', ''),
            'card_type': ext.get('Card Type', ''),
            'hp': ext.get('HP', ''),
            'stage': ext.get('Stage', ''),
            'card_text': ext.get('CardText', ''),
            'attack_1': ext.get('Attack 1', ''),
            'attack_2': ext.get('Attack 2', ''),
            'weakness': ext.get('Weakness', ''),
            'resistance': ext.get('Resistance', ''),
            'retreat_cost': ext.get('RetreatCost', ''),
            'variant': sub,
            'variant_code': variant_code,
            'is_card': is_card,
            'is_stamped': False,
            'market_usd': price_data.get('marketPrice', ''),
            'low_usd': price_data.get('lowPrice', ''),
            'mid_usd': price_data.get('midPrice', ''),
            'high_usd': price_data.get('highPrice', ''),
            'tcgplayer_image_url': product.get('imageUrl', ''),
            'tcgplayer_url': product.get('url', ''),
            'artist': ext.get('Artist', ''),
            'regulation_mark': ext.get('Regulation Mark', ''),
            'tcgplayer_modified': product.get('modifiedOn', ''),
            'bible_built_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description='PokeBulk SA - Fetch Single Set Into Bible-Format Sheet v1.0')
    parser.add_argument('--group-id', type=int, default=24688, help='TCGCSV group ID (default: 24688 = Pitch Black)')
    parser.add_argument('--set-code', type=str, default='PBL', help='Your internal set_code (default: PBL)')
    parser.add_argument('--era', type=str, default='Mega Evolution', help='Era label (default: Mega Evolution)')
    parser.add_argument('--set-name', type=str, default=None, help='Set name (default: auto from TCGCSV, else "ME05: Pitch Black")')
    parser.add_argument('--out-dir', type=str, default=DEFAULT_OUT_DIR, help='Output directory')
    args = parser.parse_args()

    print('=' * 60)
    print('PokeBulk SA - Fetch Single Set Into Bible-Format Sheet v1.0')
    print('Timestamp: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('=' * 60 + '\n')

    print('Looking up group name on TCGCSV...')
    tcgcsv_name, tcgcsv_abbr = get_group_name(args.group_id)
    set_name = args.set_name or tcgcsv_name or 'ME05: Pitch Black'
    print('  TCGCSV name       : ' + (tcgcsv_name or '(not found)'))
    print('  TCGCSV abbreviation: ' + (tcgcsv_abbr or '(not found)') + '  (informational only -- your set_code stays as given)')
    print('  Using set_name    : ' + set_name)
    print('  Using set_code    : ' + args.set_code)
    print('  Using era         : ' + args.era + '\n')

    print('Fetching products for group_id=' + str(args.group_id) + '...')
    try:
        data = fetch_json(TCGCSV_PRODUCTS.format(group_id=args.group_id))
    except Exception as e:
        print('ERROR fetching products: ' + str(e))
        sys.exit(1)

    products = data.get('results', [])
    print('  ' + str(len(products)) + ' product(s) found\n')

    if not products:
        print('No products returned -- nothing to write. The set may not be populated on')
        print('TCGCSV yet, or the group_id may be wrong. Nothing was saved.')
        sys.exit(0)

    print('Fetching prices...')
    prices_by_id = fetch_prices(args.group_id)
    time.sleep(DELAY_SECS)

    unmapped_variants = set()
    all_rows = []
    card_count = 0
    sealed_count = 0
    for p in products:
        rows = build_rows(p, prices_by_id, args.set_code, args.era, set_name, args.group_id, unmapped_variants)
        all_rows.extend(rows)
        if rows and rows[0]['is_card']:
            card_count += 1
        else:
            sealed_count += 1

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, args.set_code + '_bible_format_check.csv')
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=BIBLE_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    print('\n' + '=' * 60)
    print('Done!')
    print('  Products (cards)  : ' + str(card_count))
    print('  Products (sealed) : ' + str(sealed_count))
    print('  Total rows written: ' + str(len(all_rows)) + '  (one row per card+variant combo)')
    print('  Saved to: ' + out_path)
    if unmapped_variants:
        print('\n  NOTE: these price subTypeNames were not in VARIANT_CODE_MAP and got')
        print('  variant_code left blank -- review and add them if they matter for this set:')
        for v in sorted(unmapped_variants):
            print('    - ' + v)
    print('\n  Columns NOT filled by this script (by design, filled by later pipeline steps):')
    print('    ptcgio_set_id, bulba_set_page, is_stamped detail, stamp_type,')
    print('    pokebulk_zar, usd_zar_rate, final_image_url, pokedex_numbers,')
    print('    legality_standard/expanded/unlimited, all bulba_*/ptcg_*/final_* columns')
    print('=' * 60)


if __name__ == '__main__':
    main()
