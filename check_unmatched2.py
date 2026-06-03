from products.models import PokemonProduct
from django.db.models import Sum

old_with_stock = PokemonProduct.objects.exclude(
    name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
).filter(stock__gt=0).select_related('card_set')

from collections import defaultdict
by_set = defaultdict(lambda: {'count': 0, 'stock': 0, 'name': '', 'samples': []})

for old in old_with_stock:
    code = old.card_set.code
    by_set[code]['count'] += 1
    by_set[code]['stock'] += old.stock
    by_set[code]['name'] = old.card_set.name
    if len(by_set[code]['samples']) < 2:
        by_set[code]['samples'].append(f"#{old.card_number} {old.name}")

for code, data in sorted(by_set.items()):
    print(f"[{code}] {data['name']}: {data['count']} cards, stock={data['stock']}", flush=True)
    for s in data['samples']:
        print(f"    {s}", flush=True)
