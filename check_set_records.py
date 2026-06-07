# check_set_records.py
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import CardSet, PokemonProduct
from django.db.models import Count

print(f"{'CODE':<12} {'ERA':<10} {'RECORDS':<10} {'NAME'}")
print("-" * 60)

sets = CardSet.objects.select_related('era').annotate(
    count=Count('products')
).order_by('era__code', 'release_date', 'code')

empty = []
has_records = []

for s in sets:
    era = s.era.code if s.era else '?'
    if s.count == 0:
        empty.append(s)
    else:
        has_records.append(s)
        print(f"{s.code:<12} {era:<10} {s.count:<10} {s.name}")

print()
print(f"SETS WITH RECORDS: {len(has_records)}")
print()
print(f"EMPTY SETS ({len(empty)}) - candidates for deletion:")
for s in empty:
    era = s.era.code if s.era else '?'
    print(f"  {s.code:<12} {era:<10} {s.name}")
