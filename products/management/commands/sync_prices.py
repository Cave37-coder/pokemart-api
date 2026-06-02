"""
PokéBulk SA — Daily Price Sync
================================
Django management command: python manage.py sync_prices

Runs daily to update ALL card variant prices from TCGCSV.
Fetches a live USD/ZAR rate on every run.

Pricing formula:
    pokebulk_zar = round_up_50c(max(market_usd × zar_rate × 1.10, R1.50))

Setup:
    1. Copy this file to: products/management/commands/sync_prices.py
    2. Add tcgplayer_product_id and variant_type fields to CardVariant model
    3. Run migration
    4. Schedule daily: python manage.py sync_prices

Railway cron (add to railway.toml):
    [cron.sync_prices]
    schedule = "0 22 * * *"
    command = "python manage.py sync_prices"
"""

import requests
import math
import time
import logging
from decimal import Decimal
from datetime import datetime
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

BASE_URL  = "https://tcgcsv.com/tcgplayer"
HEADERS   = {"User-Agent": "PokeBulkSA/1.0.0"}
DELAY     = 0.15
MARKUP    = Decimal('1.10')
MINIMUM   = Decimal('1.50')
FALLBACK_ZAR = 18.50

GROUPID_TO_CODE = {
    22880:'PRIZEPACK', 3179:'TK1', 23266:'TK2', 23561:'TK24',
    22873:'SVI',   23120:'PAL',   23228:'OBF',   23237:'MEW',
    23286:'PAR',   23353:'PAF',   23381:'TEF',   23473:'TWM',
    23529:'SFA',   23537:'SCR',   23651:'SSP',   23821:'PRE',
    24073:'JTG',   24269:'DRI',   24325:'BLK',   24326:'WHT',
    22872:'SVP',   24382:'SVE',
    2585:'SWSH01', 2626:'SWSH02', 2675:'SWSH03', 2701:'SWSH04',
    2765:'SWSH05', 2807:'SWSH06', 2848:'SWSH07', 2906:'SWSH08',
    2948:'SWSH09', 3040:'SWSH10', 3118:'SWSH11', 3170:'SWSH12',
    17688:'CRZ',   17689:'CRZGG', 2685:'CHP',    2754:'SHF',
    2781:'SHFSV',  2867:'CLB',    2931:'CCC',    3064:'PGO',
    3068:'ASRTG',  3172:'LORTG',  17674:'ST',    3020:'BST',
    24380:'MEG',   24448:'PFL',   24541:'ASC',   24587:'POR',
    24655:'CRI',   24688:'ME05',  24451:'MEP',   24461:'MEE',
    1863:'SM01',   1919:'SM02',   1957:'SM03',   2071:'SM04',
    2178:'SM05',   2209:'SM06',   2278:'CES',    2295:'DRM',
    2328:'SM8',    2377:'SM9',    2420:'SM10',   2464:'SM11',
    2480:'HIF',    2594:'HIFSV',  2534:'SM12',   2054:'SHL',   1861:'SMP',
    1387:'XY',     1464:'FLF',    1481:'FFI',    1494:'PHF',
    1509:'PRC',    1525:'DCR',    1534:'ROS',    1576:'AOR',
    1661:'BKT',    1701:'BKP',    1780:'FCO',    1815:'STS',
    1842:'EVO',    1728:'GEN',    1522:'KSS',
    1400:'BLW',    1424:'EPO',    1385:'NVI',    1412:'NXD',
    1386:'DEX',    1394:'DRX',    1408:'BCR',    1413:'PLS',
    1382:'PLF',    1370:'PLB',    1409:'LTR',    1426:'DRV',
    1402:'HS',     1399:'UL',     1403:'UD',     1381:'TM',    1415:'CoL',
    1430:'DP',     1368:'MT',     1380:'SW',     1405:'GE',
    1390:'MD',     1417:'LA',     1369:'SF',     1406:'PL',
    1367:'RR',     1384:'SV',     1391:'AR',
    1393:'RS',     1392:'SS',     1376:'DR',     1377:'MA',
    1416:'HL',     1419:'RG',     1428:'TRR',    1404:'DX',
    1410:'EM',     1398:'UF',     1429:'DS',     1378:'LM',
    1379:'HP',     1395:'CG',     1411:'DF',     1383:'PK',
    604:'BS',      1663:'BSS',    635:'JU',      630:'FO',
    605:'BS2',     1373:'TR',     1441:'G1',     1440:'G2',
    1396:'N1',     1434:'N2',     1389:'N3',     1444:'N4',
    1374:'LC',     1375:'EX',     1397:'AQ',     1372:'SK',    648:'SI1',
}

VARIANT_MAP = {
    'Normal':               'Normal',
    'Holofoil':             'Holofoil',
    'Reverse Holofoil':     'Reverse Holofoil',
    '1st Edition':          '1st Edition',
    '1st Edition Holofoil': '1st Edition Holofoil',
    'Unlimited':            'Unlimited',
    'Unlimited Holofoil':   'Unlimited Holofoil',
}


def get_live_zar_rate():
    sources = [
        {"name":"Frankfurter","url":"https://api.frankfurter.app/latest?from=USD&to=ZAR","extract":lambda d:d["rates"]["ZAR"]},
        {"name":"ExchangeRate-API","url":"https://open.er-api.com/v6/latest/USD","extract":lambda d:d["rates"]["ZAR"]},
        {"name":"fawazahmed0","url":"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json","extract":lambda d:d["usd"]["zar"]},
    ]
    for s in sources:
        try:
            r = requests.get(s["url"], headers=HEADERS, timeout=10)
            if r.status_code == 200:
                rate = float(s["extract"](r.json()))
                if 10.0 < rate < 35.0:
                    return rate
        except Exception as e:
            logger.warning(f"FX {s['name']}: {e}")
    logger.error(f"All FX sources failed — using fallback R{FALLBACK_ZAR}")
    return FALLBACK_ZAR


def pokebulk_price(market_usd, zar_rate):
    """market_usd × zar_rate × 1.10, min R1.50, round UP to R0.50"""
    if not market_usd or Decimal(str(market_usd)) <= 0:
        return MINIMUM
    raw = Decimal(str(market_usd)) * Decimal(str(zar_rate)) * MARKUP
    price = max(raw, MINIMUM)
    # Round UP to nearest R0.50 using Decimal arithmetic
    import math as _math
    return Decimal(str(_math.ceil(float(price) * 2) / 2))


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}: {e}")
        time.sleep(1 * (attempt + 1))
    return None


class Command(BaseCommand):
    help = 'Sync card prices daily from TCGCSV. Applies live USD/ZAR rate + PokeBulk markup.'

    def add_arguments(self, parser):
        parser.add_argument('--set-code', type=str, help='Sync one set only (e.g. SWSH06)')
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    def handle(self, *args, **options):
        from products.models import CardVariant

        start = datetime.now()
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"PokéBulk Price Sync — {start.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"{'='*60}")

        # Live FX rate — fetched ONCE per sync run
        self.stdout.write("\nFetching live USD/ZAR rate...")
        zar_rate = get_live_zar_rate()
        self.stdout.write(f"Rate: R{zar_rate:.4f} per USD")
        self.stdout.write(f"Markup: 10% | Minimum: R1.50 | Round: UP to R0.50\n")

        # Build lookup: (set_code, product_id, variant_type) → CardVariant
        self.stdout.write("Building CardVariant lookup...")
        variant_lookup = {}
        qs = CardVariant.objects.select_related('card__card_set').filter(
            tcgplayer_product_id__isnull=False
        )
        for cv in qs:
            key = (
                cv.card.card_set.code,
                int(cv.tcgplayer_product_id),
                cv.variant_type,
            )
            variant_lookup[key] = cv
        self.stdout.write(f"Variants with productId: {len(variant_lookup)}\n")

        # Filter to specific set if requested
        if options['set_code']:
            target = options['set_code'].upper()
            groups = {gid: code for gid, code in GROUPID_TO_CODE.items() if code == target}
        else:
            groups = GROUPID_TO_CODE

        stats = {'updated': 0, 'not_found': 0, 'no_price': 0, 'errors': 0, 'groups': 0}
        updates = []

        for gid, set_code in groups.items():
            self.stdout.write(f"  {set_code:12} (groupId {gid})...", ending=' ')

            prices_data = fetch(f"{BASE_URL}/3/{gid}/prices")
            time.sleep(DELAY)

            if not prices_data:
                self.stdout.write("ERROR")
                stats['errors'] += 1
                continue

            stats['groups'] += 1
            g_updated = 0
            g_missing = 0

            for pe in prices_data['results']:
                pid      = pe['productId']
                sub_type = pe.get('subTypeName', 'Normal')
                variant  = VARIANT_MAP.get(sub_type, sub_type)
                market   = pe.get('marketPrice')
                low      = pe.get('lowPrice')

                if not market:
                    stats['no_price'] += 1
                    continue

                key = (set_code, pid, variant)
                cv = variant_lookup.get(key)

                if cv:
                    new_zar = pokebulk_price(market, zar_rate)
                    if not options['dry_run']:
                        cv.market_usd    = Decimal(str(market))
                        cv.low_usd       = Decimal(str(low)) if low else None
                        cv.pokebulk_zar  = new_zar
                        cv.usd_zar_rate  = Decimal(str(round(zar_rate, 4)))
                        updates.append(cv)
                    g_updated += 1
                    stats['updated'] += 1
                else:
                    g_missing += 1
                    stats['not_found'] += 1

            self.stdout.write(f"✓ {g_updated} updated, {g_missing} missing")

        # Bulk save all at once
        if updates and not options['dry_run']:
            self.stdout.write(f"\nSaving {len(updates)} updates...")
            with transaction.atomic():
                CardVariant.objects.bulk_update(
                    updates,
                    ['market_usd', 'low_usd', 'pokebulk_zar', 'usd_zar_rate'],
                    batch_size=500,
                )

        duration = (datetime.now() - start).seconds
        self.stdout.write(f"""
{'='*60}
SYNC COMPLETE
{'='*60}
USD/ZAR rate:      R{zar_rate:.4f}
Groups synced:     {stats['groups']}
Variants updated:  {stats['updated']}
Not in DB:         {stats['not_found']}
No price data:     {stats['no_price']}
Errors:            {stats['errors']}
Duration:          {duration}s
Dry run:           {options['dry_run']}
{'='*60}
""")
        if stats['not_found'] > 500:
            self.stdout.write(self.style.WARNING(
                f"WARNING: {stats['not_found']} variants not found in DB.\n"
                f"Run build_tcgcsv_bible.py and reimport to fix."
            ))
