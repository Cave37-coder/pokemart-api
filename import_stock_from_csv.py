# -*- coding: utf-8 -*-
"""
import_stock_from_csv.py
Imports stock quantities from old store CSV export.
Matches by set code + card number + variant.
NEVER touches price, enrichment data.

Usage:
  python import_stock_from_csv.py --dry-run
  python import_stock_from_csv.py

Run with DATABASE_URL uncommented in .env
"""
import os, django, csv, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from django.db import transaction

CSV_FILE = "store_data_20260518_140458.csv"

SET_CODE_MAP = {
    "sv1":    "SVI",
    "sv2":    "PAL",
    "sv3":    "OBF",
    "sv3pt5": "MEW",
    "sv4":    "PAR",
    "sv4pt5": "PAF",
    "sv5":    "TEF",
    "sv6":    "TWM",
    "sv6pt5": "SFA",
    "sv7":    "SCR",
    "sv8":    "SSP",
    "sv8pt5": "PRE",
    "sv9":    "JTG",
    "sv10":   "DRI",
    "swsh1":  "SWSH01",
    "swsh2":  "SWSH02",
    "swsh3":  "SWSH03",
    "swsh4":  "SWSH04",
    "swsh5":  "SWSH05",
    "swsh6":  "SWSH06",
    "swsh7":  "SWSH07",
    "swsh8":  "SWSH08",
    "swsh9":  "SWSH09",
    "swsh10": "SWSH10",
    "swsh11": "SWSH11",
    "swsh12": "SWSH12",
    "sm1":    "SM01",
    "sm2":    "SM02",
    "sm3":    "SM03",
    "sm4":    "SM04",
    "sm5":    "SM05",
    "sm6":    "SM06",
    "sm7":    "CES",
    "sm75":   "DRM",
    "sm8":    "SM8",
    "sm9":    "SM9",
    "sm10":   "SM10",
    "sm11":   "SM11",
    "sm12":   "SM12",
    "sm35":   "SHL",
    "sm115":  "HIF",
    "sma":    "HIFSV",
    "xy0":    "KSS",
    "xy1":    "XY",
    "xy2":    "FLF",
    "xy3":    "FFI",
    "xy4":    "PHF",
    "xy5":    "PRC",
    "xy6":    "ROS",
    "xy7":    "AOR",
    "xy8":    "BKT",
    "xy9":    "BKP",
    "xy10":   "FCO",
    "xy11":   "STS",
    "xy12":   "EVO",
    "dc1":    "DCR",
    "g1":     "GEN",
    "bw1":    "BLW",
    "bw2":    "EPO",
    "bw3":    "NVI",
    "bw4":    "NXD",
    "bw5":    "DEX",
    "bw6":    "DRX",
    "bw7":    "BCR",
    "bw8":    "PLS",
    "bw9":    "PLF",
    "bw10":   "PLB",
    "bw11":   "LTR",
    "dv1":    "DRV",
    "dp1":    "DP",
    "dp2":    "MT",
    "dp3":    "SW",
    "dp4":    "GE",
    "dp5":    "MD",
    "dp6":    "LA",
    "dp7":    "SF",
    "pl1":    "PL",
    "pl2":    "RR",
    "pl3":    "SV",
    "pl4":    "AR",
    "hgss1":  "HS",
    "hgss2":  "UL",
    "hgss3":  "UD",
    "hgss4":  "TM",
    "col1":   "CoL",
    "base1":  "BS",
    "base2":  "JU",
    "base3":  "FO",
    "base4":  "BS2",
    "base5":  "TR",
    "base6":  "LC",
    "basep":  "BSS",
    "gym1":   "G1",
    "gym2":   "G2",
    "neo1":   "N1",
    "neo2":   "N2",
    "neo3":   "N3",
    "neo4":   "N4",
    "ecard1": "EX",
    "ecard2": "AQ",
    "ecard3": "SK",
    "ex1":    "RS",
    "ex2":    "SS",
    "ex3":    "DR",
    "ex4":    "MA",
    "ex5":    "HL",
    "ex6":    "RG",
    "ex7":    "TRR",
    "ex8":    "DX",
    "ex9":    "EM",
    "ex10":   "UF",
    "ex11":   "DS",
    "ex12":   "LM",
    "ex13":   "HP",
    "ex14":   "CG",
    "ex15":   "DF",
    "ex16":   "PK",
    "pgo":    "PGO",
    "cel25":  "CLB",
    "swsh9tg":  "BRSTG",
    "swsh10tg": "ASRTG",
    "swsh11tg": "LORTG",
    "swsh12tg": "SITTG",
    "swsh12pt5gg": "CRZGG",
    "swsh45sv":   "SHFSV",
    "swsh45":     "SHF",
    "swsh35":     "CPA",
    "swsh12pt5":  "CRZ",
    "me1":    "MEG",
    "me2":    "PFL",
    "me2pt5": "ASC",
    "me3":    "POR",
    "me4":    "CRI",
}

VARIANT_MAP = {
    "norm":    "N",
    "normal":  "N",
    "rev":     "RH",
    "reverse": "RH",
    "holo":    "H",
    "holofoil":"H",
    "radiant": "H",
    "rainbow": "H",
    "gold":    "H",
    "secret":  "H",
    "alt":     "H",
    "full":    "H",
    "hyper":   "H",
    "special": "H",
}


def parse_sku(sku):
    """
    Parse SKU like sv1-1-norm or swsh9-186-holo
    Returns (set_code, card_number, variant) or None
    """
    sku = sku.strip().lower()
    parts = sku.split("-")
    if len(parts) < 3:
        return None

    variant_suffix = parts[-1]
    card_num_str   = parts[-2]
    set_prefix     = "-".join(parts[:-2])

    set_code = SET_CODE_MAP.get(set_prefix)
    if not set_code:
        return None

    try:
        card_number = int(card_num_str)
    except ValueError:
        return None

    variant = VARIANT_MAP.get(variant_suffix)
    if not variant:
        return None

    return set_code, card_number, variant


dry_run = "--dry-run" in sys.argv

print("Stock Import from CSV")
print(f"File: {CSV_FILE}")
print(f"Dry run: {dry_run}")
print("=" * 60)

matched    = 0
not_found  = 0
zero_qty   = 0
parse_errs = []
to_update  = []

with open(CSV_FILE, encoding='utf-8', errors='replace') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sku     = row.get('sku', '').strip()
        qty_str = row.get('quantity', '0').strip()

        if not sku:
            continue

        try:
            qty = int(float(qty_str))
        except ValueError:
            qty = 0

        if qty == 0:
            zero_qty += 1
            continue

        parsed = parse_sku(sku)
        if not parsed:
            parse_errs.append(sku)
            continue

        set_code, card_number, variant = parsed

        product = PokemonProduct.objects.filter(
            card_set__code=set_code,
            card_number=card_number,
            variant_override=variant
        ).first()

        if not product:
            not_found += 1
            if not_found <= 20:
                print(f"  NOT FOUND: {sku} -> {set_code} #{card_number} {variant}")
            continue

        if dry_run:
            print(
                f"  MATCH: {sku} -> {set_code} #{card_number} {variant} "
                f"| {(product.name or '')[:30]} | qty={qty}"
            )
            matched += 1
            continue

        product.stock = qty
        to_update.append(product)
        matched += 1

        if len(to_update) >= 200:
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(
                    to_update, ['stock'], batch_size=200
                )
            print(f"  Saved {len(to_update)} records...")
            to_update = []

if to_update and not dry_run:
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(
            to_update, ['stock'], batch_size=200
        )

print(f"\n{'='*60}")
print(f"DONE")
print(f"  Matched and updated: {matched}")
print(f"  Zero quantity (skipped): {zero_qty}")
print(f"  Not found in DB: {not_found}")
print(f"  Parse errors: {len(parse_errs)}")

if parse_errs[:20]:
    print(f"\nPARSE ERRORS (first 20):")
    for e in parse_errs[:20]:
        print(f"  {e}")
