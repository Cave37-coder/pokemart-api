import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import CardSet
from django.db.models import Count

sets = CardSet.objects.annotate(
    card_count=Count("products")
).order_by("release_date")

empty = sets.filter(card_count=0)
print(f"Empty sets: {empty.count()}")
for s in empty:
    print(f"  [{s.code}] {s.name} — {s.release_date}")

print()
print(f"Sets with cards: {sets.filter(card_count__gt=0).count()}")
