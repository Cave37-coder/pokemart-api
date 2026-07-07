# PokeBulk SA - Merge Set Into Bible
# v1.0
#
# Appends a new set's rows (e.g. the PBL sheet after Bulbapedia enrichment
# and R2 image migration) into the real pokebulk_bible_vN.csv, saving as
# the next version. Refuses to duplicate a set_code that's already present
# unless you explicitly allow it.
#
# Save to: C:\Users\texca\pokemart-api\merge_set_into_bible_v1.0.py
#
# Usage:
#   python merge_set_into_bible_v1.0.py --bible pokebulk_bible_v6.csv --new PBL_bible_format_check_expanded_bulba_enriched_r2.csv --set-code PBL --new-version 7
#   python merge_set_into_bible_v1.0.py --bible pokebulk_bible_v6.csv --new ... --set-code PBL --new-version 7 --dry-run
#   python merge_set_into_bible_v1.0.py --bible pokebulk_bible_v6.csv --new ... --set-code PBL --new-version 7 --replace-existing

import csv
import os
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description='Merge a new set into the real bible CSV')
    parser.add_argument('--bible', required=True, help='Current bible CSV (e.g. pokebulk_bible_v6.csv)')
    parser.add_argument('--new', required=True, help='New set sheet to merge in (bible-format CSV)')
    parser.add_argument('--set-code', required=True, help='The set_code being merged in, used for the duplicate check')
    parser.add_argument('--new-version', required=True, help='Version number for the output filename, e.g. 7 -> pokebulk_bible_v7.csv')
    parser.add_argument('--out-dir', default=None, help='Output directory (default: same folder as --bible)')
    parser.add_argument('--dry-run', action='store_true', help='Report what would happen, write nothing')
    parser.add_argument('--replace-existing', action='store_true', help='If set_code already exists in the bible, remove those old rows before appending the new ones')
    args = parser.parse_args()

    if not os.path.isfile(args.bible):
        print('ERROR: bible file not found: ' + args.bible)
        return
    if not os.path.isfile(args.new):
        print('ERROR: new set file not found: ' + args.new)
        return

    with open(args.bible, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        bible_columns = reader.fieldnames
        bible_rows = list(reader)

    with open(args.new, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        new_columns = reader.fieldnames
        new_rows = list(reader)

    print('Current bible: ' + str(len(bible_rows)) + ' rows, ' + str(len(bible_columns)) + ' columns')
    print('New set sheet: ' + str(len(new_rows)) + ' rows, ' + str(len(new_columns)) + ' columns')

    missing_in_new = [c for c in bible_columns if c not in new_columns]
    extra_in_new = [c for c in new_columns if c not in bible_columns]
    if missing_in_new:
        print('\nNOTE: these bible columns are not in the new sheet, will be blank for new rows:')
        for c in missing_in_new:
            print('  - ' + c)
    if extra_in_new:
        print('\nWARNING: these columns are in the new sheet but not in the bible schema, will be DROPPED:')
        for c in extra_in_new:
            print('  - ' + c)

    existing_rows_for_set = [r for r in bible_rows if r.get('set_code', '').strip() == args.set_code]
    if existing_rows_for_set:
        print('\n' + args.set_code + ' already has ' + str(len(existing_rows_for_set)) + ' row(s) in the current bible.')
        if not args.replace_existing:
            print('Refusing to proceed -- this would create duplicates.')
            print('Re-run with --replace-existing if you want to remove the old rows and replace them,')
            print('or double check you meant to merge this set at all.')
            return
        print('--replace-existing given: the old rows will be removed before appending the new ones.')

    # Build the output row set
    if args.replace_existing:
        kept_rows = [r for r in bible_rows if r.get('set_code', '').strip() != args.set_code]
    else:
        kept_rows = list(bible_rows)

    # Align new rows to the bible's exact column set/order
    aligned_new_rows = []
    for row in new_rows:
        aligned = {col: row.get(col, '') for col in bible_columns}
        aligned_new_rows.append(aligned)

    final_rows = kept_rows + aligned_new_rows

    out_dir = args.out_dir or os.path.dirname(args.bible) or '.'
    out_path = os.path.join(out_dir, 'pokebulk_bible_v' + str(args.new_version) + '.csv')

    print('\n' + '=' * 60)
    print('Plan:')
    print('  Rows kept from current bible : ' + str(len(kept_rows)))
    print('  New rows to append           : ' + str(len(aligned_new_rows)))
    print('  Total rows in output         : ' + str(len(final_rows)))
    print('  Output file                  : ' + out_path)
    print('=' * 60)

    if args.dry_run:
        print('\nDRY RUN -- nothing written. Re-run without --dry-run to save.')
        return

    if os.path.isfile(out_path):
        print('\nERROR: ' + out_path + ' already exists -- refusing to overwrite.')
        print('Choose a different --new-version or move/delete the existing file first.')
        return

    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=bible_columns)
        writer.writeheader()
        writer.writerows(final_rows)

    print('\nSaved: ' + out_path)
    print('Original ' + args.bible + ' was NOT modified -- it is still there as a fallback.')


if __name__ == '__main__':
    main()
