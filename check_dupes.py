from products.models import CardSet
codes = ['SWSH01', 'SSH', 'SWSH02', 'RCL', 'BST']
found = CardSet.objects.filter(code__in=codes)
[print(c.code, '| id=', c.pk, '| name=', c.name, '| products=', c.pokemonproduct_set.count()) for c in found]
print('Codes that exist:', list(found.values_list('code', flat=True)))
print('Codes missing:', [c for c in codes if c not in found.values_list('code', flat=True)])
