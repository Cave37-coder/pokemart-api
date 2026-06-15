import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet
from django.db.models import Count

# Find all sets with duplicate card_number + variant combinations
dupes = (PokemonProduct.objects
    .values("card_set_id", "card_number", "variant_override")
    .annotate(count=Count("id"))
    .filter(count__gt=1)
    .order_by("-count"))

total_dupe_sets = dupes.count()
total_dupe_records = sum(d["count"] for d in dupes)
print(f"Duplicate combinations: {total_dupe_sets}")
print(f"Total records in dupes: {total_dupe_records}")
print()
print("Sample duplicates:")
for d in list(dupes)[:10]:
    cs = CardSet.objects.get(id=d["card_set_id"])
    print(f"  {cs.code}  card_number={d['card_number']}  variant={d['variant_override']}  count={d['count']}")
