from products.models import PokemonProduct
from django.db.models import Count

wrong = PokemonProduct.objects.filter(
    variant_override='N',
    rarity__in=['holo_rare','ultra_rare','illustration_rare','special_illustration_rare','hyper_rare','secret_rare']
).values('card_set__code').annotate(c=Count('id')).order_by('-c')

print('Sets with wrong N on H-only rarities:')
total = 0
for r in wrong:
    print(r['card_set__code'], ':', r['c'], 'wrong N records')
    total += r['c']
print('Total wrong N records:', total)
