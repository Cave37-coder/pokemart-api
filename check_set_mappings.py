from products.models import CardSet, PokemonProduct
from django.db.models import Count

# Check all sets and their product counts
sets = CardSet.objects.select_related('era').order_by('era__code', 'release_date')
print(f"{'Code':<12} {'Name':<35} {'Cards':>6} {'Legal':>6}")
print("-"*65)
for s in sets:
    count = PokemonProduct.objects.filter(card_set=s).count()
    legal = PokemonProduct.objects.filter(card_set=s, legal_standard=True).count()
    print(f"{s.code:<12} {s.name[:33]:<35} {count:>6} {legal:>6}")
