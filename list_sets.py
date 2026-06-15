from products.models import CardSet
from django.db.models import Count
sets = CardSet.objects.annotate(pc=Count('products')).order_by('release_date','code')
for s in sets:
    era = s.era.code if s.era else 'NO ERA'
    print(s.code.ljust(12), s.name.ljust(40), era.ljust(8), str(s.release_date), str(s.pc) + ' products')
