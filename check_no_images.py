import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db.models import Count, Q

no_image = PokemonProduct.objects.filter(Q(image_url="") | Q(image_url__isnull=True))
total = no_image.count()

by_set = no_image.values("card_set__code", "card_set__name").annotate(count=Count("id")).order_by("-count")[:20]

print(f"Total cards needing images: {total}")
print()
for row in by_set:
    print(f"  {row['card_set__code']:15} {row['card_set__name']:40} {row['count']}")
