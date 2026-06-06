"""
variant_audit_and_fix_all.py

Applies the Iron Rule to ALL sets:
  Every Common/Uncommon/Rare MUST have BOTH N and RH variants.
  Holo Rares = H only. Ultra Rares/EX/GX/V/IR/SIR/HR = single print.

ORDER:
1. Read Railway records for set
2. Apply Iron Rule - find violations
3. Fetch TCGCSV to find missing variants
4. Create confirmed missing variants
5. Verify Iron Rule satisfied
6. Update prices on confirmed records

Run with DATABASE_URL uncommented in .env
Usage: python variant_audit_and_fix_all.py [SET_CODE]
       python variant_audit_and_fix_all.py  (runs all sets)
"""
import os, django, requests, sys, re, math
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet, Category
from django.utils import timezone
from collections import defaultdict
from decimal import Decimal

HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
BASE = "https://tcgcsv.com/tcgplayer/3"
MARKUP = Decimal("1.10")

# Full GROUP_CONFIG from sync_tcgcsv.py
GROUP_CONFIG = {
    "BS":       604,   "BS2":  605,   "FO":   630,   "JU":   635,
    "SI1":      648,   "TR":   1373,  "G1":   1441,  "G2":   1440,
    "N1":       1396,  "N2":   1434,  "N3":   1389,  "N4":   1444,
    "LC":       1374,  "BSS":  1663,
    "EX":       1375,  "AQ":   1397,  "SK":   1372,
    "RS":       1393,  "SS":   1392,  "DR":   1376,  "MA":   1377,
    "HL":       1416,  "RG":   1419,  "TRR":  1428,  "DS":   1429,
    "EM":       1410,  "UF":   1398,  "DF":   1411,  "CG":   1395,
    "HP":       1379,  "LM":   1378,  "PK":   1383,
    "DP":       1430,  "MT":   1368,  "SW":   1380,  "GE":   1405,
    "MD":       1390,  "LA":   1417,  "SF":   1369,
    "PL":       1406,  "RR":   1367,  "SV":   1384,  "AR":   1391,
    "HS":       1402,  "UL":   1399,  "UD":   1403,  "TM":   1381,
    "CL":       1415,
    "BLW":      1400,  "EPO":  1424,  "NVI":  1385,  "NXD":  1412,
    "DEX":      1386,  "DRX":  1394,  "DRV":  1426,  "BCR":  1408,
    "PLS":      1413,  "PLF":  1382,  "PLB":  1370,  "LTR":  1409,
    "KSS":      1522,  "XY":   1387,  "FLF":  1464,  "FFI":  1481,
    "PHF":      1494,  "PRC":  1509,  "DCR":  1525,  "ROS":  1534,
    "AOR":      1576,  "BKT":  1661,  "BKP":  1701,  "GEN":  1728,
    "FCO":      1780,  "STS":  1815,  "EVO":  1842,
    "SUM":      1863,  "GRI":  1919,  "BUS":  1957,  "SLG":  2054,
    "CIN":      2071,  "UPR":  2178,  "FLI":  2209,  "CES":  2278,
    "DRM":      2295,  "LOT":  2328,  "TEU":  2377,  "UNB":  2420,
    "UNM":      2464,  "HIF":  2480,  "CEC":  2534,
    "SSH":      2585,  "RCL":  2626,  "DAA":  2675,  "CPA":  2685,
    "VIV":      2701,  "SHF":  2754,  "BST":  2765,  "CRE":  2807,
    "EVS":      2848,  "CEL":  2867,  "FST":  2906,  "BRS":  2948,
    "ASR":      3040,  "PGO":  3064,  "LOR":  3118,  "SIT":  3170,
    "CRZ":      17688,
    "SVI":      22873, "PAL":  23120, "OBF":  23228, "MEW":  23237,
    "PAR":      23286, "PAF":  23353, "TEF":  23381, "TWM":  23473,
    "SFA":      23529, "SCR":  23537, "SSP":  23651, "PRE":  23821,
    "JTG":      24073, "DRI":  24269, "BLK":  24325, "WHT":  24326,
    "MEG":      24380, "PFL":  24448, "ASC":  24541,
    "POR":      24587, "CRI":  24655,
}

SUBTYPE_MAP = {
    "Normal":               "N",
    "Holofoil":             "H",
    "Reverse Holofoil":     "RH",
    "1st Edition Normal":   "N",
    "1st Edition Holofoil": "H",
    "Unlimited Normal":     "N",
    "Unlimited Holofoil":   "H",
    "1st Edition":          "N",
    "Unlimited":            "N",
    "":                     "H",
}

VSORT = {
    "N":0,"H":1,"RH":2,"PB":3,"MB":4,"LB":5,"FB":6,
    "QB":7,"UB":8,"DB":9,"TR":10,"SE":11,"PBP":12,"MBP":13,"CC":14,"TT":15,
}

REQUIRES_BOTH = {'common','uncommon','rare'}
SINGLE_PRINT = {
    'ultra_rare','holo_rare','illustration_rare','special_illustration_rare',
    'hyper_rare','shiny_rare','shiny_ultra_rare','secret_rare','double_rare','ace_spec_rare',
}

NUMBER_PATTERN = re.compile(r'\s*-\s*\d{3}(/\d{3,4})?\s*$')

# Fetch live rate
print("Fetching live USD/ZAR rate...")
USD_ZAR = Decimal("16.30")
try:
    r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
    USD_ZAR = Decimal(str(r.json()["rates"]["ZAR"]))
    print(f"Live rate: 1 USD = R{USD_ZAR:.4f}")
except:
    print(f"Using default rate: R{USD_ZAR}")

def zar_price(usd):
    if not usd or float(usd) <= 0:
        return Decimal("1.50")
    raw = Decimal(str(usd)) * USD_ZAR * MARKUP
    return Decimal(math.ceil(float(max(Decimal("1.50"), raw)) * 2)) / 2

def clean_name(name):
    return NUMBER_PATTERN.sub('', name or '').strip()

def parse_card_number(num_str):
    if not num_str:
        return None
    raw = str(num_str).split('/')[0].strip()
    try:
        return int(raw)
    except:
        m = re.match(r'^[A-Za-z]+(\d+)$', raw)
        return int(m.group(1)) if m else None

try:
    cat = Category.objects.get(slug="pokemon-card")
except:
    cat = Category.objects.first()

# Determine which sets to process
filter_code = sys.argv[1].upper() if len(sys.argv) > 1 else None
if filter_code:
    if filter_code not in GROUP_CONFIG:
        print(f"Unknown set code: {filter_code}")
        sys.exit(1)
    sets_to_process = {filter_code: GROUP_CONFIG[filter_code]}
else:
    sets_to_process = GROUP_CONFIG

grand = {'violations': 0, 'created': 0, 'price_updated': 0, 'sets_ok': 0, 'sets_fixed': 0, 'sets_not_in_db': 0}

for set_code, gid in sets_to_process.items():

    # Check if set exists in DB
    try:
        db_set = CardSet.objects.get(code=set_code)
    except CardSet.DoesNotExist:
        grand['sets_not_in_db'] += 1
        continue

    # STEP 1: Read Railway records
    all_records = list(PokemonProduct.objects.filter(card_set=db_set).values(
        'id', 'tcgcsv_product_id', 'card_number', 'variant_override', 'rarity', 'name', 'price'
    ))

    if not all_records:
        continue

    # Group by card_number
    by_cardnum = defaultdict(list)
    for r in all_records:
        if r['card_number'] is not None:
            by_cardnum[r['card_number']].append(r)

    # STEP 2: Iron Rule check
    missing_pairs = []
    for cnum, records in sorted(by_cardnum.items()):
        variants = {r['variant_override'] for r in records}
        rarity = (records[0]['rarity'] or '').lower()
        name = records[0]['name'] or ''

        if 'CC' in variants or 'Code Card' in name:
            continue
        if rarity in SINGLE_PRINT:
            continue

        if rarity in REQUIRES_BOTH or rarity == '':
            has_n = 'N' in variants
            has_rh = 'RH' in variants
            if not has_n or not has_rh:
                missing = []
                if not has_n: missing.append('N')
                if not has_rh: missing.append('RH')
                missing_pairs.append({
                    'card_number': cnum,
                    'name': name,
                    'rarity': rarity,
                    'has': list(variants),
                    'missing': missing,
                    'tcgcsv_product_id': records[0]['tcgcsv_product_id'],
                })

    if not missing_pairs:
        grand['sets_ok'] += 1
        # Still update prices
        r3 = requests.get(f"{BASE}/{gid}/prices", headers=HEADERS, timeout=30)
        if r3.status_code == 200:
            price_updated = 0
            for row in r3.json().get("results", []):
                pid = row["productId"]
                sub = row.get("subTypeName") or ""
                vo = SUBTYPE_MAP.get(sub, "N")
                market = row.get("marketPrice") or row.get("midPrice") or 0
                if not market: continue
                zar = zar_price(market)
                try:
                    p = PokemonProduct.objects.get(card_set=db_set, tcgcsv_product_id=pid, variant_override=vo)
                    if round(float(p.price), 2) != float(zar):
                        p.price = zar
                        if vo == "H": p.price_holo = zar
                        elif vo == "RH": p.price_reverse_holo = zar
                        elif vo == "N": p.price_normal = zar
                        p.save(update_fields=['price','price_holo','price_normal','price_reverse_holo'])
                        price_updated += 1
                except (PokemonProduct.DoesNotExist, PokemonProduct.MultipleObjectsReturned):
                    pass
            grand['price_updated'] += price_updated
        print(f"{set_code}: OK ({len(all_records)} records) | prices updated: {price_updated}")
        continue

    # Has violations
    grand['violations'] += len(missing_pairs)
    grand['sets_fixed'] += 1
    print(f"\n{set_code}: {len(missing_pairs)} Iron Rule violations | {len(all_records)} records in Railway")

    # STEP 3: Fetch TCGCSV
    r2 = requests.get(f"{BASE}/{gid}/products", headers=HEADERS, timeout=30)
    r3 = requests.get(f"{BASE}/{gid}/prices", headers=HEADERS, timeout=30)
    if r2.status_code != 200 or r3.status_code != 200:
        print(f"  TCGCSV fetch failed: products={r2.status_code} prices={r3.status_code}")
        continue

    products_raw = r2.json().get("results", [])
    prices_raw = r3.json().get("results", [])

    # Build TCGCSV maps
    tcg_prod_map = {}
    tcg_by_number = defaultdict(list)
    for p in products_raw:
        pid = p["productId"]
        name = clean_name((p.get("name") or "").strip())
        number = ""
        rarity = ""
        for ed in p.get("extendedData", []):
            if ed["name"] == "Number": number = ed["value"]
            if ed["name"] == "Rarity": rarity = ed["value"]
        cnum = parse_card_number(number)
        tcg_prod_map[pid] = {"name": name, "number": number, "rarity": rarity, "cnum": cnum}
        if cnum is not None:
            tcg_by_number[cnum].append(pid)

    tcg_price_map = defaultdict(dict)
    for row in prices_raw:
        pid = row["productId"]
        sub = row.get("subTypeName") or ""
        vo = SUBTYPE_MAP.get(sub, "N")
        market = row.get("marketPrice") or row.get("midPrice") or 0
        tcg_price_map[pid][vo] = market

    # STEP 4: Create missing variants
    created = 0
    not_found = 0

    for missing in missing_pairs:
        cnum = missing['card_number']
        pids = tcg_by_number.get(cnum, [])

        if not pids:
            not_found += 1
            continue

        for needed_vo in missing['missing']:
            found_pid = None
            found_price = 0

            for pid in pids:
                prices = tcg_price_map.get(pid, {})
                if needed_vo in prices:
                    found_pid = pid
                    found_price = prices[needed_vo]
                    break
            if not found_pid and pids:
                found_pid = pids[0]

            pb_id = f"TCGCSV-{found_pid}-{needed_vo}"
            if PokemonProduct.objects.filter(pb_id=pb_id).exists():
                p = PokemonProduct.objects.get(pb_id=pb_id)
                if p.card_number is None:
                    p.card_number = cnum
                    p.save(update_fields=['card_number'])
                continue

            zar = zar_price(found_price)
            prod_name = clean_name(tcg_prod_map[found_pid]['name']) if found_pid in tcg_prod_map else missing['name']

            try:
                PokemonProduct.objects.create(
                    pb_id=pb_id,
                    name=prod_name,
                    description=prod_name,
                    card_number=cnum,
                    variant_override=needed_vo,
                    variant_sort=VSORT.get(needed_vo, 0),
                    rarity=missing['rarity'],
                    price=zar,
                    price_normal=zar if needed_vo=="N" else None,
                    price_reverse_holo=zar if needed_vo=="RH" else None,
                    price_holo=zar if needed_vo=="H" else None,
                    tcgcsv_product_id=found_pid,
                    card_set=db_set,
                    category=cat,
                    stock=0,
                    is_active=True,
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                created += 1
            except Exception as e:
                print(f"  ERROR #{cnum} {needed_vo}: {e}")

    grand['created'] += created
    print(f"  Created: {created} | Not found: {not_found}")

    # STEP 5: Verify
    all_after = list(PokemonProduct.objects.filter(card_set=db_set).values(
        'card_number','variant_override','rarity','name'
    ))
    by_num_after = defaultdict(list)
    for r in all_after:
        if r['card_number'] is not None:
            by_num_after[r['card_number']].append(r)

    still = 0
    for cnum, records in by_num_after.items():
        variants = {r['variant_override'] for r in records}
        rarity = (records[0]['rarity'] or '').lower()
        name = records[0]['name'] or ''
        if 'CC' in variants or 'Code Card' in name: continue
        if rarity in SINGLE_PRINT: continue
        if rarity in REQUIRES_BOTH or rarity == '':
            if 'N' not in variants or 'RH' not in variants:
                still += 1
    if still == 0:
        print(f"  Iron Rule SATISFIED for {set_code} ✓")
    else:
        print(f"  WARNING: {still} cards still violating Iron Rule in {set_code}")

    # STEP 6: Update prices
    price_updated = 0
    for row in prices_raw:
        pid = row["productId"]
        sub = row.get("subTypeName") or ""
        vo = SUBTYPE_MAP.get(sub, "N")
        market = row.get("marketPrice") or row.get("midPrice") or 0
        if not market: continue
        zar = zar_price(market)
        try:
            p = PokemonProduct.objects.get(card_set=db_set, tcgcsv_product_id=pid, variant_override=vo)
            if round(float(p.price), 2) != float(zar):
                p.price = zar
                if vo == "H": p.price_holo = zar
                elif vo == "RH": p.price_reverse_holo = zar
                elif vo == "N": p.price_normal = zar
                p.save(update_fields=['price','price_holo','price_normal','price_reverse_holo'])
                price_updated += 1
        except (PokemonProduct.DoesNotExist, PokemonProduct.MultipleObjectsReturned):
            pass
    grand['price_updated'] += price_updated
    print(f"  Prices updated: {price_updated} | Final count: {PokemonProduct.objects.filter(card_set=db_set).count()}")

print(f"\n{'='*60}")
print(f"GRAND SUMMARY:")
print(f"  Sets OK (Iron Rule satisfied):  {grand['sets_ok']}")
print(f"  Sets fixed:                     {grand['sets_fixed']}")
print(f"  Sets not in DB:                 {grand['sets_not_in_db']}")
print(f"  Total violations found:         {grand['violations']}")
print(f"  Total variants created:         {grand['created']}")
print(f"  Total prices updated:           {grand['price_updated']}")
print(f"  Rate: 1 USD = R{USD_ZAR:.4f} + 10% markup")
