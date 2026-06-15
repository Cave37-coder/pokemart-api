from products.models import PokemonProduct, CardSet

# Old records: name does NOT end with (Normal), (Reverse Holo), (Holofoil) etc
# New records: name ends with (Normal), (Reverse Holo), (Holofoil) etc
# Old records were imported WITHOUT variant in name
# New records have variant appended

import re

variant_pattern = re.compile(r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$')

old_style = PokemonProduct.objects.exclude(name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$')
new_style = PokemonProduct.objects.filter(name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$')

print(f"Old style records (no variant in name): {old_style.count()}")
print(f"New style records (variant in name): {new_style.count()}")

# Check how many old style have stock > 0
old_with_stock = old_style.filter(stock__gt=0)
print(f"Old style WITH stock > 0: {old_with_stock.count()}")

# Show sets that have old style records
from django.db.models import Count
sets_with_old = old_style.values('card_set__code', 'card_set__name').annotate(count=Count('id')).order_by('-count')
print(f"\nSets with old-style records:")
for s in sets_with_old[:20]:
    print(f"  [{s['card_set__code']}] {s['card_set__name']}: {s['count']} records")
