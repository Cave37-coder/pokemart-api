import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet

total    = PokemonProduct.objects.count()
active   = PokemonProduct.objects.filter(is_active=True).count()
priced   = PokemonProduct.objects.filter(price__gt=0).count()
stamped  = PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True).count()
no_price = PokemonProduct.objects.filter(price=0).count()
sets     = CardSet.objects.count()

print(f"Total cards:          {total:,}")
print(f"Active:               {active:,}")
print(f"Priced (>R0):         {priced:,}")
print(f"Stamped w/ tcgcsv_id: {stamped:,}")
print(f"Needs manual price:   {no_price:,}")
print(f"Total sets:           {sets}")
