"""
audit_set_variants.py -- PokeBulk SA   (READ-ONLY, changes nothing)

For the My Sets checklists: does every card in every set carry all the variants it should, and are the
promo cards that belong to a set (Prerelease / Staff / stamped / ETB / Cosmos Holo) attached to it?

 1. RH gaps:  for each set, if most of its Common/Uncommon cards have a Reverse Holo row (an "RH set"),
              every Common/Uncommon/Rare card WITHOUT one is listed as a missing variant.
 2. Base gaps: cards with neither an N nor an H row.
 3. Promo linkage: promo-set rows named like "Arcanine - 12/99 (Prerelease) [Staff]" -- works out which
              parent set they belong to (same card number + printed total) and counts them per set.

Writes: set_variant_gaps.csv, promo_linkage.csv
  python manage.py shell -c "exec(open('audit_set_variants.py').read())"
"""
import csv
import re
from collections import defaultdict, Counter

from products.models import CardSet, PokemonProduct

PROMO_PREFIXES = ('PR-', 'SVP', 'MEP', 'SMP', 'SWSHP', 'XYP', 'BWP', 'DPP', 'HSP', 'WCD', 'MCD', 'TK', 'TT', 'PRIZEPACK', 'POP')
RH_RARITIES = {'common', 'uncommon', 'rare'}


def base_name(n):
    n = re.sub(r"\s*[\(\[].*$", "", n or "")
    n = re.sub(r"\s+-\s+\S*\d.*$", "", n)
    return n.strip().lower()


sets = {s.code: s for s in CardSet.objects.all()}
rows = (PokemonProduct.objects.filter(is_active=True, condition='NM')
        .values('id', 'card_set__code', 'card_number', 'name', 'rarity', 'variant_override', 'supertype'))

by_set = defaultdict(lambda: defaultdict(set))   # code -> (num, name) -> {variants}
meta = {}
for r in rows:
    code = r['card_set__code']
    if not code:
        continue
    key = (r['card_number'], base_name(r['name']))
    by_set[code][key].add((r['variant_override'] or 'N'))
    meta[(code,) + key] = (r['name'], r['rarity'])

gaps = []
print(f'{"SET":<10}{"cards":>6}{"RH set?":>9}{"missing RH":>12}{"no N/H":>8}')
for code in sorted(by_set):
    if code.startswith(PROMO_PREFIXES):
        continue
    cards = by_set[code]
    elig = [(k, v) for k, v in cards.items() if meta[(code,) + k][1] in ('common', 'uncommon')]
    with_rh = sum(1 for _, v in elig if 'RH' in v)
    rh_set = bool(elig) and with_rh / len(elig) >= 0.5
    miss_rh = no_base = 0
    for k, v in cards.items():
        name, rarity = meta[(code,) + k]
        if not (v & {'N', 'H'}):
            no_base += 1
            gaps.append([code, k[0], name, rarity, ','.join(sorted(v)), 'no N/H'])
        if rh_set and rarity in RH_RARITIES and 'RH' not in v:
            miss_rh += 1
            gaps.append([code, k[0], name, rarity, ','.join(sorted(v)), 'missing RH'])
    if miss_rh or no_base:
        print(f'{code:<10}{len(cards):>6}{"yes" if rh_set else "no":>9}{miss_rh:>12}{no_base:>8}')

with open('set_variant_gaps.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['set', 'card_number', 'name', 'rarity', 'has_variants', 'gap'])
    w.writerows(gaps)
print(f'\n{len(gaps)} variant gap(s) -> set_variant_gaps.csv')

# ---- promo linkage ----
STAMP = re.compile(r'\b(prerelease|staff|stamped|stamp|promo|exclusive|winner|league|cup|championship|worlds)\b', re.I)
NUMTOT = re.compile(r'(\d+)\s*/\s*(\d+)')
by_total = defaultdict(list)
for s in sets.values():
    if s.total_cards:
        by_total[s.total_cards].append(s.code)

linked = Counter()
link_rows = []
from django.db.models import Q
_q = Q()
for _p in PROMO_PREFIXES[:9]:
    _q |= Q(card_set__code__startswith=_p)
promos = PokemonProduct.objects.filter(_q, is_active=True).values('id', 'card_set__code', 'name', 'card_number')
for p in promos:
    m = NUMTOT.search(p['name'] or '')
    parent = ''
    if m:
        num, tot = int(m.group(1)), int(m.group(2))
        cands = [c for c in by_total.get(tot, []) if (num, base_name(p['name'])) in by_set.get(c, {})]
        if len(cands) == 1:
            parent = cands[0]
            linked[parent] += 1
    link_rows.append([p['id'], p['card_set__code'], p['name'], parent])
with open('promo_linkage.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['product_id', 'promo_set', 'name', 'parent_set_guess'])
    w.writerows(link_rows)
print(f'\nPromo rows examined: {len(link_rows)} | with a confident parent set: {sum(linked.values())}')
print('Promos per parent set (top 25):', ', '.join(f'{c}({n})' for c, n in linked.most_common(25)))
print('-> promo_linkage.csv')
