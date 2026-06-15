import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db.models import Count

orphans = PokemonProduct.objects.filter(tcgcsv_product_id__isnull=True, price=0)
by_set = orphans.values('card_set__code', 'card_set__name').annotate(count=Count('id')).order_by('-count')[:30]
print(f'Top 30 sets with orphaned records:')
for row in by_set:
    print(f"  {row['card_set__code']:15} {row['card_set__name']:40} {row['count']}")
