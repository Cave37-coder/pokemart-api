import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from django.db.models import Count

variants = PokemonProduct.objects.values('variant_override').annotate(count=Count('id')).order_by('-count')
print("variant_override values in DB:")
for v in variants:
    print(f"  {repr(v['variant_override'])}: {v['count']}")
