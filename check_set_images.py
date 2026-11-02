"""
check_set_images.py -- PokeBulk SA. Read-only "copies" check for one set's bible-format CSV.

Run it AFTER Bulbapedia enrichment and AFTER the R2 image step (and again before syncing to the DB).
It never changes anything; it only reports. Michael, 2026-11-02: "These 3 are IR's, not copies -- be careful
with the image downloads and the rarities!"

Checks, per card row (is_card == True):
  1. Same final_image_url used by two different product_id/variant combos        -> a copy
  2. Same bulba_image_filename used by two different card numbers                -> a copy
  3. Bulbapedia page title whose number does not match the card's own number     -> wrong print
  4. Card has no final_image_url (or one that is not on images.pokebulk.co.za)   -> not hosted on R2
  5. Rarity sanity: same card name with several numbers must NOT all carry one rarity when the number
     is above the set total (cards numbered above the total are the IR/SIR/Hyper chase prints).

Usage:  python check_set_images.py --in DLR_..._r2.csv
"""
import argparse
import collections
import csv
import re

R2 = 'https://images.pokebulk.co.za/'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(a.inp, encoding='utf-8-sig')) if r.get('is_card', '').strip().lower() == 'true']
    print(f'{len(rows)} card rows read')
    problems = 0

    by_final = collections.defaultdict(set)
    by_file = collections.defaultdict(set)
    for r in rows:
        key = (r['product_id'], r['variant_code'])
        if r.get('final_image_url'):
            by_final[r['final_image_url']].add(key)
        if r.get('bulba_image_filename'):
            by_file[r['bulba_image_filename']].add(r['number'])

    for url, keys in by_final.items():
        if len(keys) > 1:
            problems += 1
            print('SAME R2 IMAGE ON DIFFERENT CARDS:', url, sorted(keys))
    for fn, nums in by_file.items():
        if len(nums) > 1:
            problems += 1
            print('SAME BULBAPEDIA FILE ON DIFFERENT NUMBERS:', fn, sorted(nums))

    for r in rows:
        title = r.get('bulba_page_title', '')
        if r.get('bulba_matched', '').lower() == 'true' and title:
            m = re.search(r'_(\d+)\)$', title)
            own = r['number'].split('/')[0].strip().lstrip('0')
            if not m or m.group(1) != own:
                problems += 1
                print(f"PAGE NUMBER MISMATCH: {r['name']} #{r['number']} matched '{title}'")
        fu = r.get('final_image_url', '')
        if not fu:
            problems += 1
            print(f"NO FINAL IMAGE: {r['name']} #{r['number']} ({r['variant_code']})")
        elif not fu.startswith(R2):
            problems += 1
            print(f"NOT ON R2: {r['name']} #{r['number']} -> {fu}")

    # rarity sanity
    over = []
    for r in rows:
        m = re.match(r'(\d+)/(\d+)', r['number'])
        if m and int(m.group(1)) > int(m.group(2)) and r['rarity'] in ('Common', 'Uncommon', 'Rare'):
            over.append((r['name'], r['number'], r['rarity']))
    for o in sorted(set(over)):
        problems += 1
        print('RARITY LOOKS WRONG (numbered above set total but Common/Uncommon/Rare):', o)

    print('\nRarity counts:', dict(collections.Counter(r['rarity'] for r in rows)))
    print('ALL CLEAR' if not problems else f'{problems} problem(s) found -- fix before syncing')


if __name__ == '__main__':
    main()
