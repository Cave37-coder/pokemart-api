import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db.models import Count

dupes = (PokemonProduct.objects
    .values("card_set_id", "card_number", "variant_override")
    .annotate(count=Count("id"))
    .filter(count__gt=1))

deleted = 0
for d in dupes:
    records = list(PokemonProduct.objects.filter(
        card_set_id=d["card_set_id"],
        card_number=d["card_number"],
        variant_override=d["variant_override"]
    ).order_by("-tcgcsv_product_id", "-price", "id"))
    
    # Keep first (has tcgcsv_product_id or highest price), delete rest
    to_delete = records[1:]
    for p in to_delete:
        p.delete()
        deleted += 1

print(f"Deleted {deleted} duplicate records")
