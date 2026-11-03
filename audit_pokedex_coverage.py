"""
audit_pokedex_coverage.py -- PokeBulk SA   (READ-ONLY, changes nothing)

The /pokedex pages list every active product whose pokedex_number (or pokedex_number_2) matches the species
(API: /api/products/?pokedex=N&min_price=0.01). A card with no pokedex_number is invisible there.
This reports which active Pokemon cards are missing a number, by set (McDonald's, Trick or Treat, Prize Packs,
promos, Cosmos Holo...), and writes every one to pokedex_missing.csv so the backfill can be planned.

  python manage.py shell -c "exec(open('audit_pokedex_coverage.py').read())"
"""
import csv
from collections import Counter, defaultdict

from django.db.models import Q
from products.models import PokemonProduct

NON_POKEMON_SUPERTYPES = {'trainer', 'energy'}
NON_POKEMON_WORDS = ('energy', 'code card', 'booster', 'pack', 'box', 'tin', 'deck', 'binder', 'sleeve', 'playmat',
                     'collection', 'bundle', 'blister', 'display', 'case', 'stadium', 'supporter', 'tool')

qs = (PokemonProduct.objects.filter(is_active=True)
      .filter(Q(pokedex_number__isnull=True) | Q(pokedex_number=0))
      .select_related('card_set'))

total_active = PokemonProduct.objects.filter(is_active=True).count()
with_dex = PokemonProduct.objects.filter(is_active=True, pokedex_number__gt=0).count()
print(f'Active products: {total_active}   with a Pokedex number: {with_dex}   without: {total_active - with_dex}\n')

by_set = defaultdict(list)
for p in qs:
    st = (p.supertype or '').strip().lower()
    if st in NON_POKEMON_SUPERTYPES:
        continue
    by_set[p.card_set.code if p.card_set_id else '(no set)'].append(p)

rows = []
print(f'{"SET":<12}{"MISSING":>8}   examples')
for code, plist in sorted(by_set.items(), key=lambda kv: -len(kv[1])):
    names = Counter(p.name for p in plist)
    print(f'{code:<12}{len(plist):>8}   ' + ', '.join(n for n, _ in names.most_common(5)))
    for p in plist:
        rows.append({'set': code, 'set_name': p.card_set.name if p.card_set_id else '', 'id': p.id, 'pb_id': p.pb_id,
                     'name': p.name, 'card_number': p.card_number, 'variant': p.variant_override,
                     'supertype': p.supertype, 'rarity': p.rarity, 'stock': p.stock})

with open('pokedex_missing.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['set', 'set_name', 'id', 'pb_id', 'name', 'card_number', 'variant', 'supertype', 'rarity', 'stock'])
    w.writeheader()
    w.writerows(rows)
print(f'\n{len(rows)} Pokemon-looking card row(s) without a Pokedex number -> pokedex_missing.csv')

# Special sets Michael named
special = [c for c in by_set if c.startswith(('MCD', 'TK', 'TT', 'PR-', 'PRIZEPACK', 'SVP', 'MEP', 'SMP', 'WCD', 'SWSH', 'SM', 'XY', 'BW', 'DP', 'HS'))]
print('\nSpecial / promo-style sets with gaps:', ', '.join(f'{c}({len(by_set[c])})' for c in sorted(special)) or 'none')

# Cosmos Holo prints
ch = PokemonProduct.objects.filter(is_active=True, variant_override='CH')
print(f'\nCosmos Holo (CH) prints: {ch.count()}   without a Pokedex number: {ch.filter(Q(pokedex_number__isnull=True) | Q(pokedex_number=0)).count()}')
