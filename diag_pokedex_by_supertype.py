import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Count
from products.models import PokemonProduct

qs = PokemonProduct.objects.filter(is_active=True, pokedex_number__isnull=True)
print("null pokedex_number, by supertype:")
for r in qs.values('supertype').annotate(n=Count('id')).order_by('-n'):
    label = r['supertype'] or '(blank)'
    print(f"  {label}: {r['n']}")
