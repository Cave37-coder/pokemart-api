import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import PokemonProduct
from django.db.models import Count
print('=== DISTINCT variant_override values ===')
variants = PokemonProduct.objects.values('variant_override').annotate(count=Count('id')).order_by('-count')
for v in variants:
    print(repr(v['variant_override']) + ' | ' + str(v['count']) + ' cards')
