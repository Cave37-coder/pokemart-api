# PokeBulk SA - Apply Pricing to Bible Sheet
# v1.1
#
# Fills in usd_zar_rate + pokebulk_zar on a bible-format CSV, for any row
# that has market_usd but is missing pokebulk_zar -- using the exact same
# formula and live-rate fallback chain as pokebulk_pricing.py (imported
# directly, not reimplemented):
#   pokebulk_zar = ceil_to_nearest_0.50( max(market_usd * zar_rate * 1.10, 1.50) )
#
# Fetches the live rate ONCE per run (not per row) and reuses it for every
# row, so pricing stays internally consistent across a set.
#
# v1.1 change (2026-09-16, Classic Collection pricing gap):
# TCGCSV's marketPrice is null for a lot of low-volume / reprint cards even
# though lowPrice/midPrice/highPrice are populated (confirmed on 28 of 30
# 30th Celebration Classic Collection cards, including Crystal Lugia at a
# ~$1,280 midPrice with a null marketPrice). Previously those rows were
# just skipped and silently sat at the R1.50 floor forever. Added
# --fallback-to-mid: when market_usd is blank, try mid_usd, then low_usd,
# then high_usd, in that order, before giving up on a row. Off by default
# so existing behavior/output for already-working sets doesn't change.
#
# Save to: C:\Users\texca\pokemart-api\apply_pokebulk_pricing.py
# Requires pokebulk_pricing.py to already be in the same folder (it is).
#
# Usage:
#   python apply_pokebulk_pricing.py --bible 30C_bible_format_check.csv --dry-run
#   python apply_pokebulk_pricing.py --bible 30C_bible_format_check.csv
#   python apply_pokebulk_pricing.py --bible 30C_bible_format_check.csv --set-code 30C
#   python apply_pokebulk_pricing.py --bible 30C_bible_format_check.csv --force
#       (--force recalculates every row with a market_usd, even ones that
#       already have a pokebulk_zar value -- useful for a same-day re-price
#       after a fresh TCGCSV pull, otherwise those rows are left untouched)
#   python apply_pokebulk_pricing.py --bible 30CC_bible_format_check.csv --fallback-to-mid
#       (use mid_usd/low_usd/high_usd for rows where TCGCSV has no marketPrice
#       at all -- needed for Classic Collection, where most cards are missing
#       marketPrice but do have the other three price points)

import csv
import argparse
from pokebulk_pricing import get_live_zar_rate, pokebulk_price


def main():
    parser = argparse.ArgumentParser(description='PokeBulk SA - Apply Pricing to Bible Sheet v1.1')
    parser.add_argument('--bible', required=True, help='Bible-format CSV to price (edited in place unless --out is given)')
    parser.add_argument('--out', default=None, help='Output path (default: overwrite --bible)')
    parser.add_argument('--set-code', default=None, help='Only price rows for this set_code (default: all rows)')
    parser.add_argument('--force', action='store_true', help='Recalculate even rows that already have a pokebulk_zar value')
    parser.add_argument('--fallback-to-mid', action='store_true',
                         help='When market_usd is blank, fall back to mid_usd, then low_usd, then high_usd')
    parser.add_argument('--dry-run', action='store_true', help='Report what would change, write nothing')
    args = parser.parse_args()

    with open(args.bible, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)

    print(f"Loaded {len(rows)} rows from {args.bible}")

    print("Fetching live USD/ZAR rate...")
    zar_rate = get_live_zar_rate()
    print(f"Using rate: R{zar_rate:.4f}\n")

    priced = skipped_no_market = skipped_already_priced = skipped_other_set = 0
    priced_from = {'market_usd': 0, 'mid_usd': 0, 'low_usd': 0, 'high_usd': 0}

    for row in rows:
        if args.set_code and row.get('set_code', '').strip() != args.set_code:
            skipped_other_set += 1
            continue

        existing_zar = (row.get('pokebulk_zar') or '').strip()
        if existing_zar and not args.force:
            skipped_already_priced += 1
            continue

        # Pick the first usable price point. market_usd always wins; the
        # fallback chain only kicks in with --fallback-to-mid, and only
        # when market_usd itself is blank.
        source_col = None
        source_val = (row.get('market_usd') or '').strip()
        if source_val:
            source_col = 'market_usd'
        elif args.fallback_to_mid:
            for col in ('mid_usd', 'low_usd', 'high_usd'):
                candidate = (row.get(col) or '').strip()
                if candidate:
                    source_col = col
                    source_val = candidate
                    break

        if not source_col:
            skipped_no_market += 1
            continue

        try:
            price_val = float(source_val)
        except ValueError:
            skipped_no_market += 1
            continue

        zar_price = pokebulk_price(price_val, zar_rate)
        row['pokebulk_zar'] = f"{zar_price:.2f}"
        row['usd_zar_rate'] = f"{zar_rate:.4f}"
        priced += 1
        priced_from[source_col] += 1

    print(f"Priced            : {priced}")
    if args.fallback_to_mid:
        print(f"  from market_usd : {priced_from['market_usd']}")
        print(f"  from mid_usd    : {priced_from['mid_usd']}")
        print(f"  from low_usd    : {priced_from['low_usd']}")
        print(f"  from high_usd   : {priced_from['high_usd']}")
    print(f"Skipped (no usable price)    : {skipped_no_market}")
    print(f"Skipped (already priced)     : {skipped_already_priced}")
    if args.set_code:
        print(f"Skipped (other set_code)     : {skipped_other_set}")

    if args.dry_run:
        print("\nDRY RUN -- nothing written. Re-run without --dry-run to save.")
        return

    out_path = args.out or args.bible
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved: {out_path}")


if __name__ == '__main__':
    main()
