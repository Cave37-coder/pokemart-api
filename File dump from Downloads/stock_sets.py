import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import PokemonProduct, CardSet
# Check what set codes actually have stock
sets_with_stock = PokemonProduct.objects.filter(stock__gt=0).values_list('card_set__code', flat=True).distinct().order_by('card_set__code')
print('=== SETS WITH STOCK ===')
for code in sets_with_stock:
    print(code)
