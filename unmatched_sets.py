from products.models import PokemonProduct
from collections import defaultdict

old = PokemonProduct.objects.exclude(
    name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
).filter(stock__gt=0).select_related('card_set')

by_set = defaultdict(lambda: {'count': 0, 'stock': 0, 'name': '', 'samples': []})
for p in old:
    c = p.card_set.code
    by_set[c]['count'] += 1
    by_set[c]['stock'] += p.stock
    by_set[c]['name'] = p.card_set.name
    if len(by_set[c]['samples']) < 2:
        by_set[c]['samples'].append(p.name)

for code in sorted(by_set.keys()):
    d = by_set[code]
    print(code, d['name'], d['count'], 'cards stock='+str(d['stock']))
    for s in d['samples']:
        print('   ', s)
