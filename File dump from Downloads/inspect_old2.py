from products.models import PokemonProduct

# Show LC old vs new side by side
print("LC OLD:", flush=True)
for p in PokemonProduct.objects.filter(card_set__code='LC', stock__gt=0).order_by('card_number')[:5]:
    print(f"  #{p.card_number} '{p.name}' stock={p.stock}", flush=True)

print("\nLC NEW:", flush=True)
for p in PokemonProduct.objects.filter(card_set__code='LC', name__regex=r'\((Normal|Holofoil|Reverse Holo)\)$').order_by('card_number')[:10]:
    print(f"  #{p.card_number} '{p.name}'", flush=True)

print("\nGEN OLD with stock:", flush=True)
for p in PokemonProduct.objects.filter(card_set__code='GEN', stock__gt=0).order_by('card_number')[:5]:
    print(f"  #{p.card_number} '{p.name}' stock={p.stock}", flush=True)

print("\nGEN NEW:", flush=True)
for p in PokemonProduct.objects.filter(card_set__code='GEN', name__regex=r'\((Normal|Holofoil|Reverse Holo)\)$').order_by('card_number')[:10]:
    print(f"  #{p.card_number} '{p.name}'", flush=True)
