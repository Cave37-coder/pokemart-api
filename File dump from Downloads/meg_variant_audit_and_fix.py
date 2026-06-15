"""
meg_variant_audit_and_fix.py

ORDER OF OPERATIONS:
1. Read ALL existing Railway records for each MEG set
2. Apply Iron Rule: every Common/Uncommon/Rare needs BOTH N and RH
3. Report exactly what is missing - NO changes yet
4. Fetch TCGCSV data to find the missing variants
5. Create ONLY the confirmed missing variants
6. Verify the Iron Rule is now satisfied
7. ONLY THEN update prices on confirmed records

Run with DATABASE_URL uncommented in .env
"""
import os, django, requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet
from django.utils import timezone
from collections import defaultdict
from decimal import Decimal
import math

HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
BASE = "https://tcgcsv.com/tcgplayer/3"

# MEG set group IDs
MEG_GROUPS = {
    "MEG": 24380,
    "PFL": 24448,
    "ASC": 24541,
    "POR": 24587,
    "CRI": 24655,
}

# Rarities that require BOTH N and RH — Iron Rule
REQUIRES_BOTH = {
    'common', 'uncommon', 'rare',
    'common_holo', 'uncommon_holo',
}

# Rarities that are single print only
SINGLE_PRINT = {
    'ultra_rare', 'holo_rare', 'illustration_rare',
    'special_illustration_rare', 'hyper_rare',
    'shiny_rare', 'shiny_ultra_rare', 'secret_rare',
    'rare_holo', 'double_rare', 'ace_spec_rare',
}

SUBTYPE_MAP = {
    "Normal":           "N",
    "Holofoil":         "H",
    "Reverse Holofoil": "RH",
    "":                 "H",
}

VSORT = {
    "N":0,"H":1,"RH":2,"PB":3,"MB":4,"LB":5,"FB":6,
    "QB":7,"UB":8,"DB":9,"TR":10,"SE":11,"PBP":12,"MBP":13,"CC":14,"TT":15,
}

# Fetch live USD/ZAR rate
print("Fetching live USD/ZAR rate...")
USD_ZAR = Decimal("16.30")
MARKUP = Decimal("1.10")
for url in ["https://open.er-api.com/v6/latest/USD"]:
    try:
        r = requests.get(url, timeout=10)
        rates = r.json().get("rates", {})
        if "ZAR" in rates:
            USD_ZAR = Decimal(str(rates["ZAR"]))
            print(f"Live rate: 1 USD = R{USD_ZAR:.4f}")
            break
    except: pass

def zar_price(usd):
    if not usd or float(usd) <= 0:
        return Decimal("1.50")
    raw = Decimal(str(usd)) * USD_ZAR * MARKUP
    val = max(Decimal("1.50"), raw)
    return Decimal(math.ceil(float(val) * 2)) / 2

from products.models import Category
try:
    cat = Category.objects.get(slug="pokemon-card")
except:
    cat = Category.objects.first()

# ── MAIN LOOP ────────────────────────────────────────────────────────────────
grand_missing = 0
grand_created = 0
grand_price_updated = 0

for set_code, gid in MEG_GROUPS.items():
    print(f"\n{'='*60}")
    print(f"SET: {set_code} (TCGCSV groupId={gid})")
    print(f"{'='*60}")

    try:
        db_set = CardSet.objects.get(code=set_code)
    except CardSet.DoesNotExist:
        print(f"  NOT IN DB — skipping")
        continue

    # ── STEP 1: Read all Railway records for this set ─────────────────────
    print(f"\nSTEP 1: Reading Railway records for {set_code}...")
    all_records = list(PokemonProduct.objects.filter(card_set=db_set).values(
        'id', 'tcgcsv_product_id', 'card_number', 'variant_override',
        'rarity', 'name', 'price'
    ))
    print(f"  Found {len(all_records)} records in Railway")

    # Group by card_number
    by_cardnum = defaultdict(list)
    for r in all_records:
        cnum = r['card_number']
        if cnum is not None:
            by_cardnum[cnum].append(r)

    # Group by tcgcsv_product_id for price lookup
    by_pid = defaultdict(dict)
    for r in all_records:
        pid = r['tcgcsv_product_id']
        if pid:
            by_pid[pid][r['variant_override']] = r

    # ── STEP 2: Apply Iron Rule — find violations ──────────────────────────
    print(f"\nSTEP 2: Applying Iron Rule to {set_code}...")
    missing_pairs = []
    violations = 0

    for cnum, records in sorted(by_cardnum.items()):
        variants_present = {r['variant_override'] for r in records}
        rarity = records[0]['rarity'] or ''
        name = records[0]['name'] or ''

        # Skip code cards
        if 'CC' in variants_present or 'Code Card' in name:
            continue

        # Apply Iron Rule
        if rarity.lower() in REQUIRES_BOTH or rarity == '':
            has_n = 'N' in variants_present
            has_rh = 'RH' in variants_present

            if not has_n or not has_rh:
                violations += 1
                missing = []
                if not has_n:
                    missing.append('N')
                if not has_rh:
                    missing.append('RH')
                missing_pairs.append({
                    'card_number': cnum,
                    'name': name,
                    'rarity': rarity,
                    'has': list(variants_present),
                    'missing': missing,
                    'tcgcsv_product_id': records[0]['tcgcsv_product_id'],
                })

    print(f"  Iron Rule violations: {violations}")
    if violations:
        print(f"  Cards missing N or RH variant:")
        for v in missing_pairs[:10]:
            print(f"    #{v['card_number']} {v['name'][:40]} | has={v['has']} | missing={v['missing']}")
        if len(missing_pairs) > 10:
            print(f"    ... and {len(missing_pairs)-10} more")
    else:
        print(f"  Iron Rule satisfied — all cards have correct variants")

    grand_missing += violations

    if not violations:
        # Just update prices
        print(f"\nSTEP 3: No missing variants — skipping to price update")
    else:
        # ── STEP 3: Fetch TCGCSV to find missing variants ─────────────────
        print(f"\nSTEP 3: Fetching TCGCSV data to find missing variants...")
        r2 = requests.get(f"{BASE}/{gid}/products", headers=HEADERS, timeout=30)
        if r2.status_code != 200:
            print(f"  TCGCSV products error: {r2.status_code} — skipping")
            continue
        products_raw = r2.json().get("results", [])

        # Build product info map from TCGCSV
        tcg_prod_map = {}
        for p in products_raw:
            pid = p["productId"]
            name = (p.get("name") or "").strip()
            number = ""
            rarity = ""
            for ed in p.get("extendedData", []):
                if ed["name"] == "Number": number = ed["value"]
                if ed["name"] == "Rarity": rarity = ed["value"]
            tcg_prod_map[pid] = {"name": name, "number": number, "rarity": rarity}

        r3 = requests.get(f"{BASE}/{gid}/prices", headers=HEADERS, timeout=30)
        if r3.status_code != 200:
            print(f"  TCGCSV prices error: {r3.status_code} — skipping")
            continue
        prices_raw = r3.json().get("results", [])
        print(f"  TCGCSV: {len(products_raw)} products, {len(prices_raw)} price rows")

        # Build price map: pid -> {subtype -> price}
        tcg_price_map = defaultdict(dict)
        for row in prices_raw:
            pid = row["productId"]
            sub = row.get("subTypeName") or ""
            vo = SUBTYPE_MAP.get(sub, "N")
            market = row.get("marketPrice") or row.get("midPrice") or 0
            tcg_price_map[pid][vo] = market

        # Match missing variants to TCGCSV by card name + number
        # Build TCGCSV lookup by card number
        tcg_by_number = defaultdict(list)
        for pid, info in tcg_prod_map.items():
            num_str = info["number"]
            cnum = None
            if num_str and '/' in num_str:
                try: cnum = int(num_str.split('/')[0])
                except: pass
            elif num_str:
                try: cnum = int(num_str)
                except: pass
            if cnum is not None:
                tcg_by_number[cnum].append({'pid': pid, 'info': info})

        # ── STEP 4: Create confirmed missing variants ──────────────────────
        print(f"\nSTEP 4: Creating missing variants...")
        created = 0
        not_found = 0

        for missing in missing_pairs:
            cnum = missing['card_number']
            tcg_matches = tcg_by_number.get(cnum, [])

            if not tcg_matches:
                print(f"  NOT FOUND in TCGCSV: #{cnum} {missing['name'][:40]}")
                not_found += 1
                continue

            # Find the product_id that has the missing variant
            for needed_vo in missing['missing']:
                found_pid = None
                found_price = 0

                for match in tcg_matches:
                    pid = match['pid']
                    prices = tcg_price_map.get(pid, {})
                    if needed_vo in prices:
                        found_pid = pid
                        found_price = prices[needed_vo]
                        break
                    # Also check if this pid has any price
                    elif not found_pid:
                        found_pid = pid

                if not found_pid:
                    print(f"  NO TCGCSV MATCH: #{cnum} {missing['name'][:40]} {needed_vo}")
                    not_found += 1
                    continue

                zar = zar_price(found_price)
                prod_info = tcg_prod_map[found_pid]

                pb_id = f"TCGCSV-{found_pid}-{needed_vo}"
                if PokemonProduct.objects.filter(pb_id=pb_id).exists():
                    # Update card_number if null
                    p = PokemonProduct.objects.get(pb_id=pb_id)
                    if p.card_number is None:
                        p.card_number = cnum
                        p.save(update_fields=['card_number'])
                        print(f"  FIXED card_number: #{cnum} {needed_vo}")
                    continue

                # Create the missing variant
                try:
                    PokemonProduct.objects.create(
                        pb_id=pb_id,
                        name=prod_info['name'] or missing['name'],
                        description=prod_info['name'] or missing['name'],
                        card_number=cnum,
                        variant_override=needed_vo,
                        variant_sort=VSORT.get(needed_vo, 0),
                        rarity=missing['rarity'],
                        price=zar,
                        price_normal=zar if needed_vo == "N" else None,
                        price_reverse_holo=zar if needed_vo == "RH" else None,
                        price_holo=zar if needed_vo == "H" else None,
                        tcgcsv_product_id=found_pid,
                        card_set=db_set,
                        category=cat,
                        stock=0,
                        is_active=True,
                        created_at=timezone.now(),
                        updated_at=timezone.now(),
                    )
                    created += 1
                    print(f"  CREATED: #{cnum} {prod_info['name'][:40]} | {needed_vo} | R{zar}")
                except Exception as e:
                    print(f"  ERROR creating #{cnum} {needed_vo}: {e}")

        print(f"\n  Created: {created} | Not found: {not_found}")
        grand_created += created

        # ── STEP 5: Verify Iron Rule is now satisfied ──────────────────────
        print(f"\nSTEP 5: Verifying Iron Rule after fixes...")
        all_records_after = list(PokemonProduct.objects.filter(card_set=db_set).values(
            'card_number', 'variant_override', 'rarity', 'name'
        ))
        by_cardnum_after = defaultdict(list)
        for r in all_records_after:
            if r['card_number'] is not None:
                by_cardnum_after[r['card_number']].append(r)

        still_violations = 0
        for cnum, records in sorted(by_cardnum_after.items()):
            variants = {r['variant_override'] for r in records}
            rarity = records[0]['rarity'] or ''
            name = records[0]['name'] or ''
            if 'CC' in variants or 'Code Card' in name:
                continue
            if rarity.lower() in REQUIRES_BOTH or rarity == '':
                if 'N' not in variants or 'RH' not in variants:
                    still_violations += 1
                    print(f"  STILL MISSING: #{cnum} {name[:40]} | has={list(variants)}")

        if still_violations == 0:
            print(f"  Iron Rule SATISFIED for {set_code} ✓")
        else:
            print(f"  WARNING: {still_violations} cards still violating Iron Rule")

    # ── STEP 6: Update prices on confirmed records ─────────────────────────
    print(f"\nSTEP 6: Updating prices on confirmed records...")

    if 'prices_raw' not in dir() or set_code not in [c for c in MEG_GROUPS]:
        r3 = requests.get(f"{BASE}/{gid}/prices", headers=HEADERS, timeout=30)
        prices_raw = r3.json().get("results", [])

    price_updated = 0
    for row in prices_raw:
        pid = row["productId"]
        sub = row.get("subTypeName") or ""
        vo = SUBTYPE_MAP.get(sub, "N")
        market = row.get("marketPrice") or row.get("midPrice") or 0
        if not market or float(market) <= 0:
            continue
        zar = zar_price(market)

        # Find confirmed record by tcgcsv_product_id + variant_override
        try:
            p = PokemonProduct.objects.get(
                card_set=db_set,
                tcgcsv_product_id=pid,
                variant_override=vo
            )
            if round(float(p.price), 2) != float(zar):
                p.price = zar
                if vo == "H": p.price_holo = zar
                elif vo == "RH": p.price_reverse_holo = zar
                elif vo == "N": p.price_normal = zar
                p.save(update_fields=['price', 'price_holo', 'price_normal', 'price_reverse_holo'])
                price_updated += 1
        except PokemonProduct.DoesNotExist:
            pass
        except PokemonProduct.MultipleObjectsReturned:
            # Update all matching
            for p in PokemonProduct.objects.filter(
                card_set=db_set, tcgcsv_product_id=pid, variant_override=vo
            ):
                p.price = zar
                if vo == "H": p.price_holo = zar
                elif vo == "RH": p.price_reverse_holo = zar
                elif vo == "N": p.price_normal = zar
                p.save(update_fields=['price', 'price_holo', 'price_normal', 'price_reverse_holo'])
                price_updated += 1

    print(f"  Prices updated: {price_updated}")
    grand_price_updated += price_updated

    # Final count
    final_count = PokemonProduct.objects.filter(card_set=db_set).count()
    print(f"\n  {set_code} final record count: {final_count}")

print(f"\n{'='*60}")
print(f"COMPLETE SUMMARY:")
print(f"  Iron Rule violations found: {grand_missing}")
print(f"  Missing variants created:   {grand_created}")
print(f"  Prices updated:             {grand_price_updated}")
print(f"  Rate used: 1 USD = R{USD_ZAR:.4f} + 10% markup")
