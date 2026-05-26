from products.models import PokemonProduct, CardSet

# Check Prize Pack sets in DB
sets = CardSet.objects.filter(code__in=['PRIZEPACK','PPS1','PPS2','PPS3','PPS4','PPS5','PPS6','PPS7','PPS8']).values('code','name','release_date')
for s in sets:
    count = PokemonProduct.objects.filter(card_set__code=s['code']).count()
    print(f"{s['code']:<12} {s['name']:<40} {str(s['release_date']):<12} cards={count}")
