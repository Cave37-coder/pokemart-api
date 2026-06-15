from products.models import CardSet
sets = CardSet.objects.filter(era__code='B7').values('code','name').order_by('name')
for s in sets:
    print(f"{s['code']:<15} {s['name']}")
