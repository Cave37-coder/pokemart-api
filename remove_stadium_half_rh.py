"""
remove_stadium_half_rh.py -- PokeBulk SA
Delta Reign's six double-card Stadium halves (Legendary Pyroduct/Summit/Trench, Left/Right) only exist as
Normal -- there is no Reverse Holo. This removes the 6 wrongly-created RH rows from:
  1. the bible CSV(s) given with --bible (writes <name>.fixed.csv, original untouched)
  2. the database (only if stock is 0 and nothing else is attached)

  python remove_stadium_half_rh.py --bible pokebulk_bible_v15.csv --bible pokebulk_bible_v15_priced.csv        # preview
  python remove_stadium_half_rh.py --bible pokebulk_bible_v15.csv --bible pokebulk_bible_v15_priced.csv --apply
"""
import argparse
import csv
import os
import re

PIDS = {'726550', '726551', '726552', '726721', '726722', '726786'}
HALF = re.compile(r'\((?:Left|Right)(?:\s+Half)?\)\s*$', re.IGNORECASE)


def fix_csv(path, apply):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        cols, rows = rd.fieldnames, list(rd)
    keep = [r for r in rows if not (r['product_id'] in PIDS and r['variant_code'] == 'RH' and HALF.search(r['name']))]
    removed = len(rows) - len(keep)
    print(f'{path}: {removed} RH row(s) to remove ({len(rows)} -> {len(keep)})')
    if apply and removed:
        out = os.path.splitext(path)[0] + '.fixed.csv'
        with open(out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(keep)
        print(f'   saved -> {out}  (rename over the original once you are happy)')


def fix_db(apply):
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from products.models import PokemonProduct
    qs = PokemonProduct.objects.filter(card_set__code='DLR', tcgcsv_product_id__in=[int(p) for p in PIDS],
                                       variant_override='RH')
    print(f'DB: {qs.count()} DLR RH row(s) on the six stadium halves')
    for p in qs:
        print(f'   {p.pb_id} {p.name} stock={p.stock} price={p.price}')
        if p.stock:
            print('   !! stock > 0 -- NOT deleting this one'); continue
        if apply:
            try:
                p.delete()
                print('   deleted')
            except Exception as e:
                print('   could not delete:', e)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--bible', action='append', default=[])
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--skip-db', action='store_true')
    a = ap.parse_args()
    for b in a.bible:
        fix_csv(b, a.apply)
    if not a.skip_db:
        fix_db(a.apply)
    if not a.apply:
        print('\nPreview only. Add --apply to make the changes.')
