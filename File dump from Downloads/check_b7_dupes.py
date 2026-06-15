from products.models import CardSet, PokemonProduct

# Old codes that are duplicates of SWSH codes
OLD_CODES = ['ASR','BRS','CHP','CRE','DAA','EVS','FST','LOR','RCL','SHF','SIT','SSH','VIV','PR-SW','CEL','CELCC']

print(f"{'Code':<12} {'Name':<35} {'Cards':>6} {'Stock':>6} {'Action'}")
print("-"*70)
for code in sorted(OLD_CODES):
    try:
        cs = CardSet.objects.get(code=code)
        cards = PokemonProduct.objects.filter(card_set__code=code).count()
        stock = PokemonProduct.objects.filter(card_set__code=code, stock__gt=0).count()
        action = "SAFE DELETE" if stock == 0 else "HAS STOCK - SKIP"
        print(f"{code:<12} {cs.name:<35} {cards:>6} {stock:>6}  {action}")
    except CardSet.DoesNotExist:
        print(f"{code:<12} NOT IN DB")
