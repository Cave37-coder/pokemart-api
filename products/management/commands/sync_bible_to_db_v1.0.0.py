# PokeBulk SA - Sync Bible v6 to Django DB
# v1.0.0
# Updates existing DB products with card data from bible v6
# Match key: tcgcsv_product_id
# Only fills empty DB fields - never overwrites existing data
# except prices which always update
#
# Save to: C:\Users\texca\pokemart-api\products\management\commands\sync_bible_to_db.py
#
# Usage:
#   python manage.py sync_bible_to_db --dry-run
#   python manage.py sync_bible_to_db
#   python manage.py sync_bible_to_db --set-code BS

import csv
import os
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import PokemonProduct, CardSet

BIBLE_PATH = os.path.join('C:\\', 'Users', 'texca', 'pokemart-api', 'pokebulk_bible_v6.csv')

# GROUP_CONFIG from sync_tcgcsv.py - group_id -> db_code
GROUP_ID_TO_CODE = {
    604: 'BS', 605: 'BS2', 630: 'FO', 635: 'JU', 648: 'SI1',
    1373: 'TR', 1441: 'G1', 1440: 'G2', 1396: 'N1', 1434: 'N2',
    1389: 'N3', 1444: 'N4', 1374: 'LC', 1663: 'BSS', 1418: 'PR-WB',
    1455: 'PR-BEST', 1375: 'EX', 1397: 'AQ', 1372: 'SK', 1393: 'RS',
    1392: 'SS', 1376: 'DR', 1377: 'MA', 1416: 'HL', 1419: 'RG',
    1428: 'TRR', 1429: 'DS', 1410: 'EM', 1398: 'UF', 1411: 'DF',
    1395: 'CG', 1379: 'HP', 1378: 'LM', 1383: 'PK', 1423: 'PR-NB',
    1422: 'POP1', 1447: 'POP2', 1442: 'POP3', 1452: 'POP4',
    1430: 'DP', 1368: 'MT', 1380: 'SW', 1405: 'GE', 1390: 'MD',
    1417: 'LA', 1369: 'SF', 1406: 'PL', 1367: 'RR', 1384: 'SV',
    1391: 'AR', 1402: 'HS', 1399: 'UL', 1403: 'UD', 1381: 'TM',
    1415: 'CoL', 1433: 'RUM', 1421: 'PR-DP', 1453: 'PR-HS',
    1439: 'POP5', 1432: 'POP6', 1414: 'POP7', 1450: 'POP8', 1446: 'POP9',
    1400: 'BLW', 1424: 'EPO', 1385: 'NVI', 1412: 'NXD', 1386: 'DEX',
    1394: 'DRX', 1426: 'DRV', 1408: 'BCR', 1413: 'PLS', 1382: 'PLF',
    1370: 'PLB', 1409: 'LTR', 1465: 'LTRRC', 1407: 'PR-BLW',
    1401: 'MCD11', 1427: 'MCD12', 1522: 'KSS', 1387: 'XY', 1464: 'FLF',
    1481: 'FFI', 1494: 'PHF', 1509: 'PRC', 1525: 'DCR', 1534: 'ROS',
    1576: 'AOR', 1661: 'BKT', 1701: 'BKP', 1728: 'GEN', 1729: 'GENRC',
    1780: 'FCO', 1815: 'STS', 1842: 'EVO', 1451: 'PR-XY',
    1692: 'MCD14', 1694: 'MCD15', 3087: 'MCD16',
    1863: 'SM01', 1919: 'SM02', 1957: 'SM03', 2054: 'SHL',
    2071: 'SM04', 2178: 'SM05', 2209: 'SM06', 2278: 'CES',
    2295: 'DRM', 2328: 'SM8', 2377: 'SM9', 2409: 'DET',
    2420: 'SM10', 2464: 'SM11', 2480: 'HIF', 2594: 'HIFSV',
    2534: 'SM12', 1861: 'PR-SM', 2148: 'MCD17', 2364: 'MCD18',
    2555: 'MCD19', 2585: 'SWSH01', 2626: 'SWSH02', 2675: 'SWSH03',
    2685: 'CHP', 2701: 'SWSH04', 2754: 'SHF', 2781: 'SHFSV',
    2765: 'SWSH05', 2782: 'MCD21', 2807: 'SWSH06', 2848: 'SWSH07',
    2867: 'CLB', 2931: 'CCC', 2906: 'SWSH08', 2948: 'SWSH09',
    3020: 'BRSTG', 3040: 'SWSH10', 3064: 'PGO', 3068: 'ASRTG',
    3118: 'SWSH11', 3172: 'LORTG', 3170: 'SWSH12', 17674: 'SITTG',
    17688: 'CRZ', 17689: 'CRZGG', 3179: 'TK22', 3150: 'MCD22',
    2545: 'PR-SWSH', 22872: 'SVP', 22873: 'SVI', 22880: 'PRIZEPACK',
    23120: 'PAL', 23228: 'OBF', 23237: 'MEW', 23266: 'TK23',
    23286: 'PAR', 23306: 'MCD23', 23323: 'TCGCL', 23353: 'PAF',
    23381: 'TEF', 23473: 'TWM', 23529: 'SFA', 23537: 'SCR',
    23561: 'TK24', 23651: 'SSP', 23821: 'PRE', 24073: 'JTG',
    24163: 'MCD24', 24269: 'DRI', 24325: 'BLK', 24326: 'WHT',
    24382: 'SVE', 24380: 'MEG', 24448: 'PFL', 24451: 'MEP',
    24461: 'MEE', 24541: 'ASC', 24587: 'POR', 24655: 'CRI',
}


def parse_attack(raw):
    if not raw:
        return '', '', ''
    raw = raw.strip()
    # Remove HTML
    raw = re.sub(r'<[^>]+>', ' ', raw).strip()
    raw = re.sub(r'\s+', ' ', raw)

    # Pattern: [cost] Name (damage)\ntext
    # or: [cost] Name\ntext
    name = ''
    damage = ''
    text = ''

    lines = raw.split('\n')
    first = lines[0].strip()

    # Extract damage from parentheses at end of first line
    dmg_match = re.search(r'\(([0-9+\-×x]+)\)\s*$', first)
    if dmg_match:
        damage = dmg_match.group(1)
        first = first[:dmg_match.start()].strip()

    # Remove energy cost prefix [xxx]
    cost_match = re.match(r'^\[[^\]]+\]\s*', first)
    if cost_match:
        first = first[cost_match.end():].strip()

    name = first
    text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''
    return name, damage, text


def parse_weakness(raw):
    if not raw:
        return '', ''
    raw = raw.strip()
    # e.g. "F" or "W×2" or "P +20"
    match = re.match(r'^([A-Za-z]+)\s*([×x+\-]?\d+)?', raw)
    if match:
        return match.group(1), match.group(2) or ''
    return raw, ''


def safe_int(val):
    if not val:
        return None
    try:
        return int(str(val).strip().split('.')[0])
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = 'Sync bible v6 card data into Django DB'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--set-code', type=str, default=None)
        parser.add_argument('--bible', type=str, default=BIBLE_PATH)
        parser.add_argument('--overwrite', action='store_true',
                            help='Overwrite existing non-empty fields')

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        set_filter = options['set_code']
        bible_path = options['bible']
        overwrite  = options['overwrite']

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('PokeBulk SA - Sync Bible to DB v1.0.0')
        self.stdout.write('Bible   : ' + bible_path)
        self.stdout.write('Dry run : ' + str(dry_run))
        self.stdout.write('Overwrite: ' + str(overwrite))
        self.stdout.write('=' * 60 + '\n')

        # Load bible
        self.stdout.write('Loading bible...')
        bible_rows = []
        with open(bible_path, newline='', encoding='utf-8-sig') as f:
            bible_rows = list(csv.DictReader(f))
        self.stdout.write('  ' + str(len(bible_rows)) + ' rows\n')

        # Build lookup: product_id -> bible row
        # Use first row per product_id (base variant)
        bible_by_pid = {}
        for row in bible_rows:
            pid = str(row.get('product_id', '')).strip()
            if pid and pid not in bible_by_pid:
                bible_by_pid[pid] = row

        # Load DB products
        self.stdout.write('Loading DB products...')
        db_qs = PokemonProduct.objects.select_related('card_set')
        if set_filter:
            db_qs = db_qs.filter(card_set__code=set_filter)
        db_products = list(db_qs)
        self.stdout.write('  ' + str(len(db_products)) + ' products\n')

        updated   = 0
        unchanged = 0
        not_found = 0
        to_update = []

        for product in db_products:
            pid = str(product.tcgcsv_product_id) if product.tcgcsv_product_id else ''
            if not pid:
                not_found += 1
                continue

            bible_row = bible_by_pid.get(pid)
            if not bible_row:
                not_found += 1
                continue

            changed = False
            fields_to_save = []

            def update_field(field, val, is_int=False):
                nonlocal changed
                if not val:
                    return
                if is_int:
                    val = safe_int(val)
                    if val is None:
                        return
                current = getattr(product, field)
                # Only update if empty or overwrite mode
                if overwrite or not current:
                    if current != val:
                        setattr(product, field, val)
                        fields_to_save.append(field)
                        changed = True

            # HP
            update_field('hp', bible_row.get('hp', ''), is_int=True)

            # Retreat cost
            update_field('retreat_cost', bible_row.get('retreat_cost', ''), is_int=True)

            # Card type → card_subtypes
            update_field('card_subtypes', bible_row.get('card_type', ''))

            # Stage → supertype
            update_field('supertype', bible_row.get('stage', ''))

            # Weakness
            wtype, wval = parse_weakness(bible_row.get('weakness', ''))
            update_field('weakness_type', wtype)
            update_field('weakness_value', wval)

            # Resistance
            rtype, rval = parse_weakness(bible_row.get('resistance', ''))
            update_field('resistance_type', rtype)
            update_field('resistance_value', rval)

            # Attack 1
            a1_raw = bible_row.get('attack_1', '')
            if a1_raw:
                a1_name, a1_dmg, a1_text = parse_attack(a1_raw)
                update_field('attack_1_name', a1_name)
                update_field('attack_1_damage', a1_dmg)
                update_field('attack_1_text', a1_text)

            # Attack 2
            a2_raw = bible_row.get('attack_2', '')
            if a2_raw:
                a2_name, a2_dmg, a2_text = parse_attack(a2_raw)
                update_field('attack_2_name', a2_name)
                update_field('attack_2_damage', a2_dmg)
                update_field('attack_2_text', a2_text)

            # Card text → description
            update_field('description', bible_row.get('card_text', ''))

            # Artist
            artist = bible_row.get('final_artist', '') or bible_row.get('artist', '')
            update_field('artist', artist)

            # Number (raw)
            update_field('number', bible_row.get('number', ''))

            # Flavour text
            update_field('flavour_text', bible_row.get('ext_FlavorText', ''))

            if changed:
                to_update.append((product, fields_to_save))
                updated += 1
            else:
                unchanged += 1

        self.stdout.write('Saving updates...')
        if not dry_run:
            saved = 0
            for product, fields in to_update:
                fields.append('updated_at')
                try:
                    product.save(update_fields=fields)
                    saved += 1
                except Exception as e:
                    self.stdout.write('  ERROR ' + str(product.tcgcsv_product_id) + ': ' + str(e))

            self.stdout.write('  Saved ' + str(saved) + ' products')

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('DRY RUN - no changes saved' if dry_run else 'Done!')
        self.stdout.write('  Updated   : ' + str(updated))
        self.stdout.write('  Unchanged : ' + str(unchanged))
        self.stdout.write('  Not found : ' + str(not_found))
        self.stdout.write('=' * 60 + '\n')
