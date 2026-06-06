"""
fix_variants_and_names.py — Complete variant fix + ex->EX name fix.
Run with DATABASE_URL uncommented in .env
"""
import os, django, csv, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from collections import Counter

BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"

VARIANT_MAP = {
    'Normal':               'N',
    'Unlimited':            'N',
    'Holofoil':             'H',
    'Unlimited Holofoil':   'H',
    '1st Edition Holofoil': 'H',
    'Reverse Holofoil':     'RH',
    '1st Edition':          'RH',
    '':                     'N',
}

# Order matters — check longer/more specific suffixes first
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
    'N': 0, 'H': 1, 'RH': 2,
    'PB': 3, 'MB': 4, 'LB': 5, 'FB': 6, 'QB': 7, 'UB': 8,
    'DB': 9, 'TR': 10, 'SE': 11,
    'PBP': 12, 'MBP': 13,
    'CC': 14, 'TT': 15,
}

print("Reading Bible CSV...")
pid_map = {}
with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        pid = row.get('product_id', '').strip()
        if not pid:
            continue
        name = row.get('name', '').strip()
        variant_str = row.get('variant', '').strip()
        is_stamped = row.get('is_stamped', '').strip()
        stamp_type = row.get('stamp_type', '').strip()

        # Code card
        if 'Code Card' in name:
            vo = 'CC'
        # TT stamped
        elif is_stamped == 'True' and 'Trick or Trade' in stamp_type:
            vo = 'TT'
        # Ball/pattern suffixes
        else:
            vo = None
            for suffix, code in BALL_SUFFIXES:
                if suffix in name:
                    vo = code
                    break
            if vo is None:
                vo = VARIANT_MAP.get(variant_str, 'N')

        pid_map[pid] = vo

print(f"Bible CSV: {len(pid_map)} entries mapped")
vc = Counter(pid_map.values())
for k, v in sorted(vc.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print()
print("Fetching products from DB...")
products = list(PokemonProduct.objects.select_related('card_set__era').all())
print(f"DB: {len(products)} products")

to_update = []
stats = Counter()
ex_fixed = 0

for p in products:
    changed = False

    # Lookup variant from Bible CSV by product_id
    pid = str(p.tcgcsv_product_id) if p.tcgcsv_product_id else None
    if not pid and p.pb_id and p.pb_id.startswith('TCGCSV-'):
        pid = p.pb_id.replace('TCGCSV-', '')

    if pid and pid in pid_map:
        new_vo = pid_map[pid]
    else:
        # Fallback: check name suffixes directly
        name = p.name or ''
        new_vo = None
        if 'Code Card' in name:
            new_vo = 'CC'
        else:
            for suffix, code in BALL_SUFFIXES:
                if suffix in name:
                    new_vo = code
                    break
        if new_vo is None:
            new_vo = p.variant_override or 'N'
            if new_vo not in VSORT:
                new_vo = 'N'

    new_vs = VSORT.get(new_vo, 0)

    if p.variant_override != new_vo or p.variant_sort != new_vs:
        p.variant_override = new_vo
        p.variant_sort = new_vs
        stats[new_vo] += 1
        changed = True

    # Fix ex -> EX for SV and MEG era
    era_code = p.card_set.era.code if p.card_set and p.card_set.era else ''
    if era_code in ('SV', 'MEG') and p.name:
        new_name = re.sub(r'\bex\b', 'EX', p.name)
        if new_name != p.name:
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
print("=" * 60)
print("DONE:")
for code in ['N','H','RH','PB','MB','LB','FB','QB','UB','DB','TR','SE','PBP','MBP','CC','TT']:
    if stats.get(code, 0) > 0:
        print(f"  {code}: {stats[code]}")
print(f"  ex->EX fixes: {ex_fixed}")
