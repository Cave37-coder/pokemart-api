import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct

total = PokemonProduct.objects.count()
active = PokemonProduct.objects.filter(is_active=True).count()
in_stock = PokemonProduct.objects.filter(stock__gt=0).count()
active_in_stock = PokemonProduct.objects.filter(is_active=True, stock__gt=0).count()

print(f"Total:           {total:,}")
print(f"Active:          {active:,}")
print(f"stock > 0:       {in_stock:,}")
print(f"Active + stock>0:{active_in_stock:,}")

# Check what stock values look like
from django.db.models import Count
stocks = PokemonProduct.objects.values("stock").annotate(count=Count("id")).order_by("-count")[:5]
print()
print("Stock value distribution:")
for s in stocks:
    print(f"  stock={s['stock']}  count={s['count']:,}")
