import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import PokemonProduct, CardSet
from django.db.models import Count

print("Sets with most cards:")
for row in PokemonProduct.objects.values("card_set__code").annotate(c=Count("id")).order_by("-c")[:20]:
    print(f"  {row['card_set__code']:15} {row['c']:,}")
