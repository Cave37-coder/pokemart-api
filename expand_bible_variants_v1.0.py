# PokeBulk SA - Expand Bible-Format Sheet With Expected Variants
# v1.0
#
# Takes a bible-format check sheet (e.g. from fetch_set_bible_format_v1.0.py)
# and adds the sibling variant rows the IRON RULE says should exist, so
# sync_bible_to_db.py creates every variant row in one pass -- no manual
# backfill needed later (same problem as the Prize Pack stamped-energy gap).
#
# IRON RULE (from products/views.py / your standing rules):
#   Every Common/Uncommon/Rare print gets N (Normal) + RH (Reverse Holo).
#   Every "Rare Holo"/"Holo Rare" print gets H (Holofoil) + RH.
#   Higher rarities (Double Rare, Ultra Rare, Illustration Rare, Special
#   Illustration Rare, Hyper Rare, ACE SPEC Rare, Secret Rare, etc.) are
#   single-print only in modern (SV/ME-era) sets -- no RH is synthesized
#   for these, since TCGCSV's single listing IS the correct final variant.
#
# Synthetic rows get blank price fields (market_usd/low_usd/mid_usd/high_usd)
# since there's no real TCGCSV price for a variant that doesn't exist as its
# own catalog entry yet -- these need pricing via stock_entry once you have
# real cards in hand, same as any other manual backfill.
#
# This script does NOT touch the DB. It only reads and writes CSV files.
#
# Save to: C:\Users\texca\pokemart-api\expand_bible_variants_v1.0.py
#
# Usage:
#   python expand_bible_variants_v1.0.py --in PBL_bible_format_check.csv
#   python expand_bible_variants_v1.0.py --in PBL_bible_format_check.csv --out PBL_expanded.csv

import csv
import argparse
import os

# rarity string (as it appears in the 'rarity' column, i.e. TCGCSV's raw
# ext_Rarity value) -> list of (variant_code, variant_label) that SHOULD
# exist for that rarity tier. Rarities not listed here are left untouched --
# their single existing row is treated as the final, correct variant.
# Rarity tiers where the IRON RULE applies: every N or H print gets a
# matching RH (Reverse Holofoil). Rarities NOT in this set are left
# completely untouched -- they're single-print (Double Rare, Ultra Rare,
# Illustration Rare, Special Illustration Rare, Hyper Rare, ACE SPEC Rare,
# Secret Rare, etc.), no RH exists for them.
#
# IMPORTANT: this script only ever ADDS RH. It never synthesizes N or H --
# whichever one TCGCSV already lists (Normal or Holofoil) IS the real print
# type for that specific card, and is left exactly as-is. A "Rare" card can
# legitimately be printed as either Normal or Holofoil; the rarity label
# alone doesn't tell you which, only TCGCSV's actual listing does.
RH_ELIGIBLE_RARITIES = {'Common', 'Uncommon', 'Rare', 'Rare Holo', 'Holo Rare'}

# These columns get blanked on any synthesized (not-yet-real) variant row,
# since there's no genuine TCGCSV price/listing for it yet.
BLANK_ON_SYNTH = [
    'market_usd', 'low_usd', 'mid_usd', 'high_usd',
    'pokebulk_zar', 'usd_zar_rate',
]


def main():
    parser = argparse.ArgumentParser(description='Expand a bible-format sheet with expected sibling variants')
    parser.add_argument('--in', dest='in_path', required=True, help='Input bible-format CSV (e.g. from fetch_set_bible_format_v1.0.py)')
    parser.add_argument('--out', dest='out_path', default=None, help='Output CSV path (default: <input>_expanded.csv)')
    args = parser.parse_args()

    if not os.path.isfile(args.in_path):
        print('ERROR: input file not found: ' + args.in_path)
        return

    out_path = args.out_path or (os.path.splitext(args.in_path)[0] + '_expanded.csv')
    manifest_path = os.path.splitext(out_path)[0] + '_added_manifest.csv'

    with open(args.in_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)

    print('Read ' + str(len(rows)) + ' row(s) from ' + args.in_path)

    # Group existing rows by product_id (same physical card, possibly
    # already split across a couple of variant rows if TCGCSV had them).
    by_product = {}
    for row in rows:
        by_product.setdefault(row['product_id'], []).append(row)

    all_out_rows = []
    added_manifest = []
    skipped_no_rule = 0

    for product_id, product_rows in by_product.items():
        is_card = product_rows[0].get('is_card', '').strip().lower() == 'true'
        rarity = product_rows[0].get('rarity', '').strip()

        # Sealed products and anything without a recognized rarity tier
        # pass through untouched.
        all_out_rows.extend(product_rows)

        if not is_card:
            continue

        if rarity not in RH_ELIGIBLE_RARITIES:
            skipped_no_rule += 1
            continue

        existing_codes = {r.get('variant_code', '').strip() for r in product_rows}

        if 'RH' in existing_codes:
            continue  # already has it, nothing to do

        if not existing_codes & {'N', 'H'}:
            # No real N or H base row to clone from (unexpected shape) --
            # skip rather than guess.
            continue

        base_row = product_rows[0]
        new_row = dict(base_row)
        new_row['variant'] = 'Reverse Holofoil'
        new_row['variant_code'] = 'RH'
        for col in BLANK_ON_SYNTH:
            if col in new_row:
                new_row[col] = ''
        all_out_rows.append(new_row)
        added_manifest.append({
            'product_id': product_id,
            'name': base_row.get('name', ''),
            'rarity': rarity,
            'added_variant': 'Reverse Holofoil',
            'added_variant_code': 'RH',
        })

    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_out_rows)

    if added_manifest:
        with open(manifest_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['product_id', 'name', 'rarity', 'added_variant', 'added_variant_code'])
            writer.writeheader()
            writer.writerows(added_manifest)

    print('\n' + '=' * 60)
    print('Done!')
    print('  Original rows       : ' + str(len(rows)))
    print('  Synthesized rows added: ' + str(len(added_manifest)))
    print('  Total rows written   : ' + str(len(all_out_rows)))
    print('  Cards with no expansion rule (left as-is): ' + str(skipped_no_rule))
    print('  Saved expanded sheet to: ' + out_path)
    if added_manifest:
        print('  Saved manifest of added rows to: ' + manifest_path)
        print('\n  NOTE: synthesized rows have blank price fields -- these are placeholders')
        print('  for variants that should exist but have no real TCGCSV listing yet.')
        print('  Price them via stock_entry once you have real cards in hand, same as')
        print('  any other manual backfill (e.g. the Prize Pack stamped-energy gap).')
    print('=' * 60)


if __name__ == '__main__':
    main()
