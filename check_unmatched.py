from products.models import PokemonProduct

old_with_stock = PokemonProduct.objects.exclude(
    name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
).filter(stock__gt=0).select_related('card_set')

unmatched = []
for old in old_with_stock:
    matched = None
    if old.name.endswith(' (Holo)'):
        base = old.name[:-7]
        matched = PokemonProduct.objects.filter(card_set=old.card_set, name=f"{base} (Holofoil)").first()
    elif old.name.endswith(' (Reverse Holo)'):
        matched = PokemonProduct.objects.filter(card_set=old.card_set, name=old.name, tcgcsv_product_id__isnull=False).first()
    else:
        matched = PokemonProduct.objects.filter(card_set=old.card_set, name=f"{old.name} (Normal)").first()
        if not matched:
            matched = PokemonProduct.objects.filter(card_set=old.card_set, name=f"{old.name} (Holofoil)").first()
    
    if not matched:
        unmatched.append(old)

# Group by set
from collections import defaultdict
by_set = defaultdict(list)
for p in unmatched:
    by_set[p.card_set.code].append(p)

print(f"Total unmatched with stock: {len(unmatched)}", flush=True)
print(f"\nBy set:", flush=True)
for code, cards in sorted(by_set.items()):
    total_stock = sum(c.stock for c in cards)
    print(f"  [{code}] {cards[0].card_set.name}: {len(cards)} cards, {total_stock} total stock", flush=True)
    for c in cards[:3]:
        print(f"    #{c.card_number} '{c.name}' stock={c.stock}", flush=True)
