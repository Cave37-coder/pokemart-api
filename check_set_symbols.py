from products.models import CardSet
sets = CardSet.objects.exclude(symbol_url='').exclude(symbol_url__isnull=True).values('code','name','symbol_url')[:10]
print(f"Sets with symbol_url: {CardSet.objects.exclude(symbol_url='').exclude(symbol_url__isnull=True).count()}")
print(f"Sets without symbol_url: {CardSet.objects.filter(symbol_url='').count()}")
for s in sets:
    print(f"  {s['code']:<12} {s['symbol_url'][:60]}")
