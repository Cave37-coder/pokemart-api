"""
label_vunion_parts.py -- PokeBulk SA. Adds "ptN" to the four pieces of each V-UNION promo in the bible.

Michael, 2026-11-02: V-UNION cards are SWSH Black Star promos, each piece has its own SWSH number, shown as
    SWSH139 - 139 pt1
    SWSH140 - 140 pt2
    SWSH141 - 141 pt3
    SWSH142 - 142 pt4
Pieces are numbered in promo-number order (Pt1 = lowest number of the block of 4).

Reads a bible CSV, finds ONLY the single-piece rows named "<Pokemon> V-UNION - SWSHnnn" (any capitalisation of
UNION), groups them per Pokemon into runs of 4 consecutive numbers, and writes a PREVIEW csv. Nothing else is
touched: the "[Set of 4]" bundles, Special Collection boxes, code cards and the un-numbered "Zacian V-UNION"
promo row are skipped. It never touches the database.

  python label_vunion_parts.py --bible pokebulk_bible_v14.csv                 # preview only
  python label_vunion_parts.py --bible pokebulk_bible_v14.csv --write pokebulk_bible_v15_vunion.csv
      (--write saves a full copy of the bible with the new names; the original file is left alone)
"""
import argparse
import csv
import re
import sys
from collections import defaultdict

PIECE = re.compile(r'^(?P<mon>.+?)\s+V-UNION\s+-\s+(?P<code>SWSH(?P<num>\d+))$', re.IGNORECASE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bible', required=True)
    ap.add_argument('--preview', default='vunion_parts_preview.csv')
    ap.add_argument('--write', default=None, help='save a full copy of the bible with the part labels applied')
    a = ap.parse_args()

    with open(a.bible, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        cols, rows = rd.fieldnames, list(rd)

    groups = defaultdict(dict)          # pokemon -> {number: product_id}
    names = {}
    for r in rows:
        m = PIECE.match((r.get('name') or '').strip())
        if m:
            mon = m.group('mon').strip().title()
            groups[mon][int(m.group('num'))] = r['product_id']
            names[r['product_id']] = (r['name'], m.group('code').upper(), int(m.group('num')), mon)

    new_name = {}
    problems = []
    for mon, nums in sorted(groups.items()):
        ordered = sorted(nums)
        # split into runs of consecutive numbers, each run should be exactly 4 long
        runs, cur = [], [ordered[0]]
        for n in ordered[1:]:
            if n == cur[-1] + 1:
                cur.append(n)
            else:
                runs.append(cur)
                cur = [n]
        runs.append(cur)
        for run in runs:
            if len(run) != 4:
                problems.append(f'{mon}: run {run[0]}-{run[-1]} has {len(run)} piece(s), expected 4 -- left unlabelled')
                continue
            for i, n in enumerate(run, 1):
                pid = nums[n]
                old, code, num, mon_t = names[pid]
                new_name[pid] = f'{mon_t} V-UNION - {code} - {num} pt{i}'

    with open(a.preview, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['product_id', 'old_name', 'new_name', 'promo_number', 'part'])
        for pid, nn in sorted(new_name.items(), key=lambda kv: (names[kv[0]][3], names[kv[0]][2])):
            old, code, num, mon = names[pid]
            w.writerow([pid, old, nn, code, nn.rsplit(' ', 1)[-1]])
    print(f'{len(new_name)} piece(s) labelled -> {a.preview}')
    for p in problems:
        print('  WARNING:', p)

    if a.write:
        n = 0
        for r in rows:
            if r['product_id'] in new_name:
                r['name'] = new_name[r['product_id']]
                if 'clean_name' in r:
                    r['clean_name'] = new_name[r['product_id']]
                n += 1
        with open(a.write, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f'{n} row(s) renamed, saved copy -> {a.write}')


if __name__ == '__main__':
    sys.exit(main())
