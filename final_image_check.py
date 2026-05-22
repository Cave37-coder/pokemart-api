import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db.models import Q

no_image = PokemonProduct.objects.filter(Q(image_url="") | Q(image_url__isnull=True)).count()
print(f"Cards with no image: {no_image}")
