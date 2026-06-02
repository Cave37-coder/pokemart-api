"""
PokéBulk SA — TCGCSV Master Bible Builder
==========================================
Run this on your LOCAL machine (not Railway — TCGCSV blocks server IPs).

Requirements:
    pip install requests

Usage:
    python build_tcgcsv_bible.py

Output files (in same directory):
    pokebulk_bible_YYYYMMDD.csv          — all products (cards + sealed)
    pokebulk_bible_cards_only_YYYYMMDD.csv — cards only

What this does:
    1. Fetches live USD/ZAR rate (3-source fallback chain)
    2. Pulls ALL 147 mapped Pokemon groups from TCGCSV
    3. For each group: fetches products + prices, joins on productId
    4. Applies PokéBulk pricing formula:
       pokebulk_zar = round_up_50c(max(market_usd × zar_rate × 1.10, R1.50))
    5. Outputs complete master Bible CSV
    6. Leaves enrichment columns blank (filled by enrichment script)

Enrichment columns to fill after (Bulbapedia + pokemontcg.io):
    bulbapedia_image_url, ptcg_image_url, final_image_url,
    artist, pokedex_numbers, regulation_mark,
    legality_standard, legality_expanded
"""

import requests
import csv
import time
import math
import logging
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://tcgcsv.com/tcgplayer"
HEADERS = {"User-Agent": "PokeBulkSA/1.0.0"}
DELAY = 0.15       # 150ms between requests — respect TCGCSV rate limits
MARKUP = 1.10      # 10% markup
MINIMUM_ZAR = 1.50 # Minimum price
FALLBACK_ZAR = 18.50


# ─────────────────────────────────────────────
# LIVE FX RATE
# ─────────────────────────────────────────────

def get_live_zar_rate():
    """Fetch live USD/ZAR rate — 3-source fallback chain, no API key needed."""
    sources = [
        {
            "name": "Frankfurter (ECB)",
            "url": "https://api.frankfurter.app/latest?from=USD&to=ZAR",
            "extract": lambda d: d["rates"]["ZAR"],
        },
        {
            "name": "ExchangeRate-API",
            "url": "https://open.er-api.com/v6/latest/USD",
            "extract": lambda d: d["rates"]["ZAR"],
        },
        {
            "name": "fawazahmed0 CDN",
            "url": "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
            "extract": lambda d: d["usd"]["zar"],
        },
    ]
    for source in sources:
        try:
            r = requests.get(source["url"], headers=HEADERS, timeout=10)
            if r.status_code == 200:
                rate = float(source["extract"](r.json()))
                if 10.0 < rate < 35.0:
                    print(f"  Live USD/ZAR: R{rate:.4f} (from {source['name']})")
                    return rate
                logger.warning(f"Suspicious rate R{rate} from {source['name']}")
        except Exception as e:
            logger.warning(f"FX source '{source['name']}' failed: {e}")
    logger.error(f"All FX sources failed — using fallback R{FALLBACK_ZAR}")
    return FALLBACK_ZAR


def pokebulk_price(market_usd, zar_rate):
    """market_usd × zar_rate × 1.10, min R1.50, round UP to R0.50"""
    if not market_usd or float(market_usd) <= 0:
        return MINIMUM_ZAR
    raw = float(market_usd) * float(zar_rate) * MARKUP
    price = max(raw, MINIMUM_ZAR)
    return math.ceil(price * 2) / 2


# ─────────────────────────────────────────────
# GROUPID MAPPING — our set code → TCGPlayer groupId
# ─────────────────────────────────────────────

GROUPID_TO_CODE = {
    # Special Sets
    22880: 'PRIZEPACK', 3179: 'TK1', 23266: 'TK2', 23561: 'TK24',
    # Scarlet & Violet
    22873: 'SVI',   23120: 'PAL',   23228: 'OBF',   23237: 'MEW',
    23286: 'PAR',   23353: 'PAF',   23381: 'TEF',   23473: 'TWM',
    23529: 'SFA',   23537: 'SCR',   23651: 'SSP',   23821: 'PRE',
    24073: 'JTG',   24269: 'DRI',   24325: 'BLK',   24326: 'WHT',
    22872: 'SVP',   24382: 'SVE',
    # Sword & Shield
    2585: 'SWSH01', 2626: 'SWSH02', 2675: 'SWSH03', 2701: 'SWSH04',
    2765: 'SWSH05', 2807: 'SWSH06', 2848: 'SWSH07', 2906: 'SWSH08',
    2948: 'SWSH09', 3040: 'SWSH10', 3118: 'SWSH11', 3170: 'SWSH12',
    17688: 'CRZ',   17689: 'CRZGG', 2685: 'CHP',    2754: 'SHF',
    2781: 'SHFSV',  2867: 'CLB',    2931: 'CCC',    3064: 'PGO',
    3068: 'ASRTG',  3172: 'LORTG',  17674: 'ST',    3020: 'BST',
    # Mega Evolution
    24380: 'MEG',   24448: 'PFL',   24541: 'ASC',   24587: 'POR',
    24655: 'CRI',   24688: 'ME05',  24451: 'MEP',   24461: 'MEE',
    # Sun & Moon
    1863: 'SM01',   1919: 'SM02',   1957: 'SM03',   2071: 'SM04',
    2178: 'SM05',   2209: 'SM06',   2278: 'CES',    2295: 'DRM',
    2328: 'SM8',    2377: 'SM9',    2420: 'SM10',   2464: 'SM11',
    2480: 'HIF',    2594: 'HIFSV',  2534: 'SM12',   2054: 'SHL',
    1861: 'SMP',
    # XY Era
    1387: 'XY',     1464: 'FLF',    1481: 'FFI',    1494: 'PHF',
    1509: 'PRC',    1525: 'DCR',    1534: 'ROS',    1576: 'AOR',
    1661: 'BKT',    1701: 'BKP',    1780: 'FCO',    1815: 'STS',
    1842: 'EVO',    1728: 'GEN',    1522: 'KSS',
    # Black & White
    1400: 'BLW',    1424: 'EPO',    1385: 'NVI',    1412: 'NXD',
    1386: 'DEX',    1394: 'DRX',    1408: 'BCR',    1413: 'PLS',
    1382: 'PLF',    1370: 'PLB',    1409: 'LTR',    1426: 'DRV',
    # HG&SS
    1402: 'HS',     1399: 'UL',     1403: 'UD',     1381: 'TM',
    1415: 'CoL',
    # Diamond & Pearl / Platinum
    1430: 'DP',     1368: 'MT',     1380: 'SW',     1405: 'GE',
    1390: 'MD',     1417: 'LA',     1369: 'SF',     1406: 'PL',
    1367: 'RR',     1384: 'SV',     1391: 'AR',
    # EX Era
    1393: 'RS',     1392: 'SS',     1376: 'DR',     1377: 'MA',
    1416: 'HL',     1419: 'RG',     1428: 'TRR',    1404: 'DX',
    1410: 'EM',     1398: 'UF',     1429: 'DS',     1378: 'LM',
    1379: 'HP',     1395: 'CG',     1411: 'DF',     1383: 'PK',
    # WotC / Base
    604:  'BS',     1663: 'BSS',    635:  'JU',     630:  'FO',
    605:  'BS2',    1373: 'TR',     1441: 'G1',     1440: 'G2',
    1396: 'N1',     1434: 'N2',     1389: 'N3',     1444: 'N4',
    1374: 'LC',     1375: 'EX',     1397: 'AQ',     1372: 'SK',
    648:  'SI1',
}

ERA_MAP = {
    'BS':'WotC Base','BSS':'WotC Base','JU':'WotC Base','FO':'WotC Base',
    'BS2':'WotC Base','TR':'WotC Base','G1':'WotC Base','G2':'WotC Base',
    'SI1':'WotC Other',
    'N1':'WotC Neo','N2':'WotC Neo','N3':'WotC Neo','N4':'WotC Neo',
    'LC':'WotC Legendary','EX':'WotC Legendary','AQ':'WotC Legendary','SK':'WotC Legendary',
    'PRIZEPACK':'Special - Prize Pack',
    'TK1':'Special - Trick or Trade','TK2':'Special - Trick or Trade','TK24':'Special - Trick or Trade',
}
for c in ['RS','SS','DR','MA','HL','RG','TRR','DX','EM','UF','DS','LM','HP','CG','DF','PK']:
    ERA_MAP[c] = 'EX Era'
for c in ['DP','MT','SW','GE','MD','LA','SF','PL','RR','SV','AR']:
    ERA_MAP[c] = 'Diamond & Pearl'
for c in ['HS','UL','UD','TM','CoL']:
    ERA_MAP[c] = 'HG&SS'
for c in ['BLW','EPO','NVI','NXD','DEX','DRX','BCR','PLS','PLF','PLB','LTR','DRV']:
    ERA_MAP[c] = 'Black & White'
for c in ['XY','FLF','FFI','PHF','PRC','DCR','ROS','AOR','BKT','BKP','FCO','STS','EVO','GEN','KSS']:
    ERA_MAP[c] = 'XY Era'
for c in ['SM01','SM02','SM03','SM04','SM05','SM06','CES','DRM','SM8','SM9','SM10',
          'SM11','HIF','HIFSV','SM12','SHL','SMP']:
    ERA_MAP[c] = 'Sun & Moon'
for c in ['SWSH01','SWSH02','SWSH03','SWSH04','SWSH05','SWSH06','SWSH07','SWSH08',
          'SWSH09','SWSH10','SWSH11','SWSH12','CRZ','CRZGG','CHP','SHF','SHFSV',
          'CLB','CCC','PGO','ASRTG','LORTG','ST','BST']:
    ERA_MAP[c] = 'Sword & Shield'
for c in ['SVI','PAL','OBF','MEW','PAR','PAF','TEF','TWM','SFA','SCR','SSP','PRE',
          'JTG','DRI','BLK','WHT','SVP','SVE']:
    ERA_MAP[c] = 'Scarlet & Violet'
for c in ['MEG','PFL','ASC','POR','CRI','ME05','MEP','MEE']:
    ERA_MAP[c] = 'Mega Evolution'

STAMP_MAP = {
    'PRIZEPACK': 'Play! Pokemon Prize Pack',
    'TK1': 'Trick or Trade Halloween 2022',
    'TK2': 'Trick or Trade Halloween 2023',
    'TK24': 'Trick or Trade Halloween 2024',
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            logger.warning(f"HTTP {r.status_code}: {url}")
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}: {e}")
        time.sleep(1 * (attempt + 1))
    return None


def ext(product, key):
    """Extract value from extendedData by key name."""
    for item in product.get('extendedData', []):
        if item['name'] == key:
            v = item['value'] or ''
            # Strip HTML tags from card text fields
            if key in ('CardText', 'Attack 1', 'Attack 2'):
                import re
                v = re.sub(r'<[^>]+>', ' ', v).strip()
                v = ' '.join(v.split())  # Normalise whitespace
            return v
    return ''


def is_card(product):
    """True if this product is an individual card (not a sealed box/pack)."""
    return bool(ext(product, 'Number') or ext(product, 'Rarity'))


# ─────────────────────────────────────────────
# MAIN BUILD
# ─────────────────────────────────────────────

FIELDNAMES = [
    # Identity
    'group_id', 'set_code', 'era', 'set_name',
    'product_id', 'name', 'clean_name', 'number',
    # Card attributes (from TCGCSV extendedData)
    'rarity', 'card_type', 'hp', 'stage',
    'card_text', 'attack_1', 'attack_2',
    'weakness', 'resistance', 'retreat_cost',
    # Variant & pricing
    'variant', 'is_card', 'is_stamped', 'stamp_type',
    'market_usd', 'low_usd', 'mid_usd', 'high_usd',
    'pokebulk_zar', 'usd_zar_rate',
    # Images (TCGCSV has its own CDN images)
    'tcgplayer_image_url', 'tcgplayer_url',
    # Enrichment — filled by enrich_bulbapedia.py
    'bulbapedia_image_url',
    # Enrichment — filled by enrich_ptcg_fallback.py
    'ptcg_image_url',
    # Final merged image — filled by merge_images.py
    'final_image_url',
    # Card detail enrichment
    'artist', 'pokedex_numbers', 'regulation_mark',
    'legality_standard', 'legality_expanded', 'legality_unlimited',
    # Meta
    'tcgplayer_modified', 'bible_built_at',
]


def build_bible():
    today = datetime.now().strftime('%Y%m%d_%H%M')
    built_at = datetime.now().isoformat()
    output_all   = f'pokebulk_bible_{today}.csv'
    output_cards = f'pokebulk_bible_cards_only_{today}.csv'

    print("=" * 60)
    print("PokéBulk SA — TCGCSV Bible Builder")
    print("=" * 60)

    # 1. Get live FX rate ONCE — use for entire run
    print("\nFetching live USD/ZAR rate...")
    zar_rate = get_live_zar_rate()
    print(f"Using rate: R{zar_rate:.4f} per USD")

    # 2. Get all groups to find set names
    print("\nFetching Pokemon groups from TCGCSV...")
    groups_data = fetch(f"{BASE_URL}/3/groups")
    if not groups_data:
        print("FAILED to fetch groups. Check internet connection.")
        return

    group_names = {g['groupId']: g['name'] for g in groups_data['results']}
    our_groups = [(gid, code) for gid, code in GROUPID_TO_CODE.items()]
    print(f"Groups to sync: {len(our_groups)}")

    all_rows = []
    stats = {'cards': 0, 'sealed': 0, 'no_price': 0, 'errors': 0}

    # 3. Pull each group
    for i, (gid, set_code) in enumerate(sorted(our_groups)):
        gname = group_names.get(gid, f'Unknown (groupId {gid})')
        era = ERA_MAP.get(set_code, 'Unknown')
        stamp_type = STAMP_MAP.get(set_code, '')
        is_stamped = bool(stamp_type)

        print(f"\n[{i+1}/{len(our_groups)}] {set_code:12} | {gname}")

        # Products
        products_data = fetch(f"{BASE_URL}/3/{gid}/products")
        time.sleep(DELAY)
        if not products_data:
            print(f"  ERROR: products fetch failed")
            stats['errors'] += 1
            continue

        products = {p['productId']: p for p in products_data['results']}

        # Prices
        prices_data = fetch(f"{BASE_URL}/3/{gid}/prices")
        time.sleep(DELAY)
        if not prices_data:
            print(f"  ERROR: prices fetch failed")
            stats['errors'] += 1
            continue

        # Build price lookup: productId → [price_entries]
        price_lookup = defaultdict(list)
        for p in prices_data['results']:
            price_lookup[p['productId']].append(p)

        card_count = 0
        sealed_count = 0

        for pid, product in products.items():
            card = is_card(product)
            prices = price_lookup.get(pid, [])

            # Base fields from product
            base = {
                'group_id':             gid,
                'set_code':             set_code,
                'era':                  era,
                'set_name':             gname,
                'product_id':           pid,
                'name':                 product['name'],
                'clean_name':           product['cleanName'],
                'number':               ext(product, 'Number'),
                'rarity':               ext(product, 'Rarity'),
                'card_type':            ext(product, 'Card Type'),
                'hp':                   ext(product, 'HP'),
                'stage':                ext(product, 'Stage'),
                'card_text':            ext(product, 'CardText')[:500],
                'attack_1':             ext(product, 'Attack 1'),
                'attack_2':             ext(product, 'Attack 2'),
                'weakness':             ext(product, 'Weakness'),
                'resistance':           ext(product, 'Resistance'),
                'retreat_cost':         ext(product, 'RetreatCost'),
                'is_card':              card,
                'is_stamped':           is_stamped,
                'stamp_type':           stamp_type,
                'tcgplayer_image_url':  product.get('imageUrl', ''),
                'tcgplayer_url':        product.get('url', ''),
                'tcgplayer_modified':   product.get('modifiedOn', ''),
                'usd_zar_rate':         round(zar_rate, 4),
                'bible_built_at':       built_at,
                # Enrichment placeholders
                'bulbapedia_image_url': '',
                'ptcg_image_url':       '',
                'final_image_url':      '',
                'artist':               '',
                'pokedex_numbers':      '',
                'regulation_mark':      '',
                'legality_standard':    '',
                'legality_expanded':    '',
                'legality_unlimited':   '',
            }

            if not prices:
                # No price — include with blank pricing
                row = {**base,
                    'variant': '', 'market_usd': '', 'low_usd': '',
                    'mid_usd': '', 'high_usd': '', 'pokebulk_zar': '',
                }
                all_rows.append(row)
                stats['no_price'] += 1
            else:
                # One row per variant (Normal / Holofoil / Reverse Holofoil etc.)
                for pe in prices:
                    market = pe.get('marketPrice')
                    low    = pe.get('lowPrice')
                    mid    = pe.get('midPrice')
                    high   = pe.get('highPrice')
                    zar    = pokebulk_price(market, zar_rate) if market else ''

                    row = {**base,
                        'variant':     pe.get('subTypeName', ''),
                        'market_usd':  market or '',
                        'low_usd':     low or '',
                        'mid_usd':     mid or '',
                        'high_usd':    high or '',
                        'pokebulk_zar': zar,
                    }
                    all_rows.append(row)

                    if card:
                        card_count += 1
                        stats['cards'] += 1
                    else:
                        sealed_count += 1
                        stats['sealed'] += 1

        print(f"  Cards: {card_count} | Sealed: {sealed_count}")

    # 4. Write CSVs
    print(f"\nWriting {len(all_rows)} rows to {output_all}...")
    with open(output_all, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    cards_only = [r for r in all_rows if r['is_card']]
    print(f"Writing {len(cards_only)} card rows to {output_cards}...")
    with open(output_cards, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(cards_only)

    print(f"""
{'='*60}
BIBLE BUILD COMPLETE
{'='*60}
USD/ZAR rate used:  R{zar_rate:.4f}
Total rows:         {len(all_rows)}
  Card rows:        {stats['cards']}
  Sealed rows:      {stats['sealed']}
  No price data:    {stats['no_price']}
Group errors:       {stats['errors']}

Output files:
  {output_all}
  {output_cards}

NEXT STEPS:
  1. Review the cards_only CSV — check prices look correct
  2. Run enrich_bulbapedia.py  → fills bulbapedia_image_url + artist + pokedex
  3. Run enrich_ptcg_fallback.py → fills ptcg_image_url for any blanks
  4. Run merge_images.py       → sets final_image_url from best source
  5. Import into Django DB
{'='*60}
""")


if __name__ == '__main__':
    build_bible()
