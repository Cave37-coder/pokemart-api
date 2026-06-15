from products.models import CardSet, PokemonProduct
from collections import defaultdict

# Find all sets with duplicate names within same era
by_era_name = defaultdict(list)
for cs in CardSet.objects.select_related('era').all():
    key = (cs.era.code if cs.era else 'NONE', cs.name)
    by_era_name[key].append(cs.code)

print("Duplicate set names within same era:")
print(f"{'Era':<6} {'Name':<40} {'Codes'}")
print("-"*70)
dupes_found = False
for (era, name), codes in sorted(by_era_name.items()):
    if len(codes) > 1:
        dupes_found = True
        cards = {c: PokemonProduct.objects.filter(card_set__code=c).count() for c in codes}
        stock = {c: PokemonProduct.objects.filter(card_set__code=c, stock__gt=0).count() for c in codes}
        codes_str = ', '.join([f"{c}({cards[c]}cards,{stock[c]}stock)" for c in codes])
        print(f"{era:<6} {name[:38]:<40} {codes_str}")

if not dupes_found:
    print("No duplicates found!")
