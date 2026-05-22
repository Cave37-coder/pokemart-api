import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db.models import Count

print("Supertype distribution:")
for row in PokemonProduct.objects.values("supertype").annotate(count=Count("id")).order_by("-count"):
    print(f"  {repr(row['supertype']):20} {row['count']:,}")

print()
print("Sample card_subtypes for Trainers:")
trainers = PokemonProduct.objects.filter(supertype="Trainer").exclude(card_subtypes="").exclude(card_subtypes__isnull=True)
print(f"  Trainers with subtypes: {trainers.count():,}")
for p in trainers[:5]:
    print(f"  {p.name[:30]:30} subtypes={repr(p.card_subtypes)}")
