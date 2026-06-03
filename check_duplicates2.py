from products.models import PokemonProduct
from django.db.models import Count
import sys

old_style = PokemonProduct.objects.exclude(
    name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
)

print(f"Old style total: {old_style.count()}", flush=True)
print(f"Old style with stock: {old_style.filter(stock__gt=0).count()}", flush=True)

print("\nOld style with stock > 0 by set:", flush=True)
for s in old_style.filter(stock__gt=0).values('card_set__code','card_set__name').annotate(c=Count('id')).order_by('-c'):
    print(f"  [{s['card_set__code']}] {s['card_set__name']}: {s['c']}", flush=True)

print("\nAll sets with old-style records:", flush=True)
for s in old_style.values('card_set__code','card_set__name').annotate(c=Count('id')).order_by('-c')[:30]:
    print(f"  [{s['card_set__code']}] {s['card_set__name']}: {s['c']}", flush=True)
