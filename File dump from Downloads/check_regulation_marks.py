from products.models import PokemonProduct, CardSet

# Check if regulation mark field exists
fields = [f.name for f in PokemonProduct._meta.get_fields()]
print("Has regulation_mark field:", 'regulation_mark' in fields)

# Check CardSet fields
cs_fields = [f.name for f in CardSet._meta.get_fields()]
print("CardSet fields:", [f for f in cs_fields if 'reg' in f.lower() or 'legal' in f.lower() or 'mark' in f.lower()])

# Check what era codes map to what regulation marks
from products.models import Era
eras = Era.objects.all().values('code','name').order_by('code')
for e in eras:
    print(f"  {e['code']:<6} {e['name']}")
