import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Q
from products.models import PokemonProduct, CardSet

# Read-only. "all promo cards, all!" -- before building one big script that
# touches every promo set at once, need the actual scope: every CardSet in
# THIS catalog that's a promo set, how many active products it has, and how
# many of those are missing/broken images right now.

sets = CardSet.objects.filter(
    Q(name__icontains='promo') | Q(code__iendswith='p')
).order_by('era__code' if hasattr(CardSet, 'era') else 'code', 'code')

print(f"{'Code':10} {'Era':8} {'Name':45} {'Active':>7} {'Blank img':>10}")
print("-" * 90)
total_active = 0
total_blank = 0
for cs in sets:
    products = PokemonProduct.objects.filter(card_set=cs, is_active=True)
    active = products.count()
    if active == 0:
        continue
    blank = products.filter(Q(image_url='') | Q(image_url__isnull=True)).count()
    era_code = cs.era.code if getattr(cs, 'era', None) else '?'
    print(f"{cs.code:10} {era_code:8} {cs.name[:45]:45} {active:>7} {blank:>10}")
    total_active += active
    total_blank += blank

print("-" * 90)
print(f"TOTAL across all promo-like sets: {total_active} active products, {total_blank} with blank image_url")
print()
print("NOTE: 'blank image_url' undercounts the real problem -- a set can have a URL")
print("stored that 404s or points at the wrong card (exactly what happened with CLB).")
print("Use this list to confirm which sets exist before we build the fetch script for each.")
