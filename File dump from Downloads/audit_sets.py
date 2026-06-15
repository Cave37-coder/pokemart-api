import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, "C:/Users/texca/pokemart-api")
django.setup()
from products.models import CardSet, PokemonProduct
print("=== SET AUDIT ===")
for cs in CardSet.objects.all().order_by("era__code", "release_date"):
    total = PokemonProduct.objects.filter(card_set=cs).count()
    priced = PokemonProduct.objects.filter(card_set=cs, price__gt=0).count()
    pct = round(priced/total*100) if total > 0 else 0
    flag = "BAD" if pct < 50 else ("WARN" if pct < 80 else "OK")
    print(f"{flag} {cs.code:12} {cs.name:35} {priced:4}/{total:4} ({pct}%)")
