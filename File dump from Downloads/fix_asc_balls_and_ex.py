"""
fix_asc_balls_and_ex.py
1. Fixes ball variant codes for ASC TCGCSV records by name suffix
2. Fixes ex->EX in SV and MEG era card names
Run with DATABASE_URL uncommented in .env
"""
import os, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from collections import Counter

BALL_SUFFIXES = [
    ('(Poke Ball Pattern)',   'PBP'),
    ('(Master Ball Pattern)', 'MBP'),
    ('(Poke Ball)',           'PB'),
    ('(Master Ball)',         'MB'),
    ('(Love Ball)',           'LB'),
    ('(Friend Ball)',         'FB'),
    ('(Quick Ball)',          'QB'),
    ('(Ultra Ball)',          'UB'),
    ('(Dusk Ball)',           'DB'),
    ('(Team Rocket)',         'TR'),
    ('(Secret)',              'SE'),
]

VSORT = {
    'N':0,'H':1,'RH':2,'PB':3,'MB':4,'LB':5,'FB':6,'QB':7,'UB':8,
    'DB':9,'TR':10,'SE':11,'PBP':12,'MBP':13,'CC':14,'TT':15,
}

print("Fetching products...")
products = list(PokemonProduct.objects.select_related('card_set__era').all())
print(f"Total: {len(products)}")

to_update = []
stats = Counter()
ex_fixed = 0

for p in products:
    changed = False
    name = p.name or ''
    era_code = p.card_set.era.code if p.card_set and p.card_set.era else ''

    # Fix ball variants by name suffix
    new_vo = None
    for suffix, code in BALL_SUFFIXES:
        if suffix in name:
            new_vo = code
            break

    if new_vo and new_vo != p.variant_override:
        p.variant_override = new_vo
        p.variant_sort = VSORT.get(new_vo, 0)
        stats[new_vo] += 1
        changed = True

    # Fix ex -> EX for SV and MEG era
    if era_code in ('SV', 'MEG'):
        new_name = re.sub(r'\bex\b', 'EX', name)
        if new_name != name:
            p.name = new_name
            ex_fixed += 1
            changed = True

    if changed:
        to_update.append(p)

print(f"Updating {len(to_update)} records...")
BATCH = 500
for i in range(0, len(to_update), BATCH):
    PokemonProduct.objects.bulk_update(to_update[i:i+BATCH], ['variant_override', 'variant_sort', 'name'])
    print(f"  Saved {min(i+BATCH, len(to_update))}/{len(to_update)}")

print()
print("=" * 50)
print("DONE:")
for code in ['PB','MB','LB','FB','QB','UB','DB','TR','SE','PBP','MBP']:
    if stats.get(code, 0):
        print(f"  {code}: {stats[code]}")
print(f"  ex->EX fixes: {ex_fixed}")
