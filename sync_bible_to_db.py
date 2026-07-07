"""
sync_bible_to_db.py — PokeBulk SA
Syncs the Bible CSV to the Railway PostgreSQL DB.

Rules:
- product_id is the unique key per variant_code
- Creates new records if (product_id, variant_code) not in DB
- Updates existing records: price, image_url, artist, pokedex_number,
  regulation_mark, legal_standard, legal_expanded if changed
- Never touches stock, orders, or ball variants already in DB
- Ball variants (PB/MB/LB/FB/QB/UB/DB/TR/SE/PBP/MBP) from Bible ARE synced
- Skips rows where is_card != True
- Skips rows where variant_code is empty

USAGE:
  python sync_bible_to_db.py --bible pokebulk_bible_v5.csv
  python sync_bible_to_db.py --bible pokebulk_bible_v5.csv --set-code SM01
  python sync_bible_to_db.py --bible pokebulk_bible_v5.csv --dry-run
  python sync_bible_to_db.py --bible pokebulk_bible_v5.csv --update-only  # only update existing
  python sync_bible_to_db.py --bible pokebulk_bible_v5.csv --create-only  # only create new
"""

import os
import sys
import django
import argparse
import pandas as pd
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet, Era, Category

VARIANT_SORT_ORDER = {
    "N": 0, "RH": 1, "H": 2, "PB": 3, "MB": 4, "LB": 5,
    "FB": 6, "QB": 7, "UB": 8, "DB": 9, "TR": 10, "SE": 11,
    "PBP": 12, "MBP": 13, "CC": 14, "TT": 15,
}

RARITY_MAP = {
    "Common":                       "common",
    "Uncommon":                     "uncommon",
    "Rare":                         "rare",
    "Holo Rare":                    "holo_rare",
    "Rare Holo":                    "holo_rare",
    "Rare Holo V":                  "holo_rare",
    "Rare Holo VMAX":               "ultra_rare",
    "Rare Holo VSTAR":              "ultra_rare",
    "Rare Holo EX":                 "ultra_rare",
    "Rare Holo GX":                 "ultra_rare",
    "Ultra Rare":                   "ultra_rare",
    "Double Rare":                  "ultra_rare",
    "Illustration Rare":            "illustration_rare",
    "Special Illustration Rare":    "special_illustration_rare",
    "Hyper Rare":                   "hyper_rare",
    "Shiny Rare":                   "shiny_rare",
    "Shiny Ultra Rare":             "shiny_ultra_rare",
    "Rare Secret":                  "secret_rare",
    "Secret Rare":                  "secret_rare",
    "Rare Rainbow":                 "hyper_rare",
    "Rare Shining":                 "holo_rare",
    "Rare Shiny":                   "shiny_rare",
    "Rare Shiny GX":                "shiny_ultra_rare",
    "Rare Prism Star":              "ultra_rare",
    "Amazing Rare":                 "ultra_rare",
    "Trainer Gallery Rare Holo":    "holo_rare",
    "Trainer Gallery Ultra Rare":   "ultra_rare",
    "Trainer Gallery Secret Rare":  "secret_rare",
    "Classic Collection":           "holo_rare",
    "ACE SPEC Rare":                "ultra_rare",
    "Mega Hyper Rare":              "hyper_rare",
    "Mega Attack Rare":             "ultra_rare",
    "Promo":                        "common",
    "Legend":                       "holo_rare",
    "Shining":                      "holo_rare",
    "Gold Star":                    "ultra_rare",
}

def clean(val, default=''):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return str(val).strip()

def to_bool(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, bool):
        return val
    return str(val).lower() in ('true', '1', 'yes')

def to_int(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(float(val))
    except:
        return None

def to_decimal(val, default=Decimal('1.50')):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return Decimal(str(val))
    except:
        return default

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bible', required=True)
    parser.add_argument('--set-code', help='Only sync this set')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--update-only', action='store_true')
    parser.add_argument('--create-only', action='store_true')
    args = parser.parse_args()

    print(f"Reading Bible: {args.bible}")
    df = pd.read_csv(args.bible, low_memory=False)
    print(f"Total rows: {len(df)}")

    # Filter
    # is_card can appear as "True"/"1"/"False" across different bible
    # versions (older rows were written as integers, not booleans) -- a
    # strict `df['is_card'] == True` silently matches ZERO rows once the
    # column has mixed string types, since pandas can't infer bool dtype.
    # Normalize instead of guessing which representation is "correct".
    is_card_normalized = df['is_card'].astype(str).str.strip().str.lower().isin(['true', '1'])
    df = df[is_card_normalized]
    df = df[df['variant_code'].notna() & (df['variant_code'] != '')]
    print(f"Card rows with variant_code: {len(df)}")

    if args.set_code:
        df = df[df['set_code'] == args.set_code]
        print(f"Filtered to {args.set_code}: {len(df)} rows")

    # Build existing lookup
    all_pids = df['product_id'].dropna().astype(int).unique().tolist()
    existing = {}
    for obj in PokemonProduct.objects.filter(tcgcsv_product_id__in=all_pids):
        existing[(obj.tcgcsv_product_id, obj.variant_override)] = obj

    print(f"Existing DB records for these products: {len(existing)}")

    # Get/cache CardSets and category
    card_sets = {cs.code: cs for cs in CardSet.objects.select_related('era').all()}
    category, _ = Category.objects.get_or_create(name="Pokemon Card")

    created = updated = skipped = errors = 0

    total_rows = len(df)
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        if idx % 500 == 0:
            print(f"  Progress: {idx}/{total_rows} | Created:{created} Updated:{updated} Skipped:{skipped} Errors:{errors}")
        try:
            product_id = int(row['product_id'])
            set_code = clean(row['set_code'])
            name = clean(row['name'])
            variant_code = clean(row['variant_code'])
            rarity_raw = clean(row['rarity'])

            if not variant_code or not set_code:
                skipped += 1
                continue

            # Map values
            rarity = RARITY_MAP.get(rarity_raw, 'common')
            price = to_decimal(row.get('pokebulk_zar'))
            image_url = clean(row.get('final_image_url'))
            card_number = to_int(row.get('card_number'))
            artist = clean(row.get('final_artist'))
            pokedex = to_int(row.get('final_pokedex') or row.get('bulba_pokedex_number'))
            reg_mark = clean(row.get('final_regulation_mark'))
            legal_std = to_bool(row.get('bulba_legality_standard'))
            legal_exp = to_bool(row.get('bulba_legality_expanded'))

            key = (product_id, variant_code)

            if key in existing:
                # UPDATE existing record
                if args.create_only:
                    skipped += 1
                    continue

                obj = existing[key]
                changed = False
                fields = []

                if price and obj.price != price:
                    obj.price = price; fields.append('price'); changed = True
                if image_url and obj.image_url != image_url:
                    obj.image_url = image_url; fields.append('image_url'); changed = True
                if card_number and obj.card_number != card_number:
                    obj.card_number = card_number; fields.append('card_number'); changed = True

                if changed:
                    if not args.dry_run:
                        fields.append('updated_at')
                        obj.save(update_fields=fields)
                    updated += 1
                else:
                    skipped += 1

            else:
                # CREATE new record
                if args.update_only:
                    skipped += 1
                    continue

                card_set = card_sets.get(set_code)
                if not card_set:
                    print(f"  WARN: CardSet {set_code} not found for {name}")
                    skipped += 1
                    continue

                if args.dry_run:
                    print(f"  [DRY CREATE] {set_code} #{card_number} {name} | {variant_code} | R{price}")
                    created += 1
                    continue

                # IMPORTANT: pb_id must include variant_code, not just product_id.
                # Without this, N/H/RH variants of the same card all resolve to
                # the same pb_id -- the first one creates a row, every sibling
                # variant after it silently collides with get_or_create and
                # just does a (usually no-op) update instead of creating its
                # own row. This is how an entire set's RH variants can vanish
                # without any error being raised.
                pb_id = f"TCGCSV-{product_id}-{variant_code}"
                obj, was_created = PokemonProduct.objects.get_or_create(
                    pb_id=pb_id,
                    defaults=dict(
                        tcgcsv_product_id=product_id,
                        name=name,
                        card_number=card_number,
                        card_set=card_set,
                        category=category,
                        variant_override=variant_code,
                        variant_sort=VARIANT_SORT_ORDER.get(variant_code, 9),
                        rarity=rarity,
                        image_url=image_url,
                        price=price,
                        stock=0,
                    )
                )
                if was_created:
                    created += 1
                else:
                    # Already exists with same pb_id — update price and image
                    obj.price = price
                    obj.image_url = image_url
                    if card_number:
                        obj.card_number = card_number
                    obj.save(update_fields=["price", "image_url", "card_number", "updated_at"])
                    updated += 1

        except Exception as e:
            print(f"  ERROR: {row.get('set_code')} {row.get('name')}: {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"DONE")
    print(f"  Created:  {created}")
    print(f"  Updated:  {updated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")

if __name__ == '__main__':
    main()
