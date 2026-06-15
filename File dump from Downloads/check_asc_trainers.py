from products.models import PokemonProduct

# Check ASC trainer RH cards
trainers = PokemonProduct.objects.filter(
    card_set__code='ASC',
    supertype='Trainer',
    variant_override='RH'
).values('card_number','variant_override','name','variant_sort')[:10]
print(f"ASC Trainer RH cards: {PokemonProduct.objects.filter(card_set__code='ASC', supertype='Trainer', variant_override='RH').count()}")
for c in trainers:
    print(f"  #{c['card_number']} {c['variant_override']} sort={c['variant_sort']} {c['name'][:30]}")

# Check variant_sort for RH
rh_sort = PokemonProduct.objects.filter(card_set__code='ASC', variant_override='RH').values('variant_sort').first()
print(f"\nRH variant_sort value: {rh_sort}")
