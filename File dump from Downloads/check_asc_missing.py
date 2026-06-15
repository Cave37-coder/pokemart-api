import csv
from products.models import PokemonProduct

# Load CSV for ASC
csv_rows = []
with open('pokebulk_cards_20260524_1558.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['abbreviation'] == 'ASC' and row['isCard'].strip().upper() == 'TRUE':
            csv_rows.append(row)

# Get DB records
db_records = set()
for p in PokemonProduct.objects.filter(card_set__code='ASC').values('card_number','variant_override'):
    db_records.add((str(p['card_number']).zfill(3), p['variant_override']))

# Find missing
missing = []
for row in csv_rows:
    num = row['number'].split('/')[0].strip().zfill(3)
    variant = row['db_variant']
    if (num, variant) not in db_records:
        missing.append(row)

print(f"CSV rows: {len(csv_rows)}")
print(f"DB records: {len(db_records)}")
print(f"Missing: {len(missing)}")
print(f"\nFirst 20 missing:")
for r in missing[:20]:
    print(f"  #{r['number'].split('/')[0].zfill(3)} {r['db_variant']:<10} {r['name'][:35]} pid={r['productId']}")

# Group by variant type
from collections import Counter
variant_counts = Counter(r['db_variant'] for r in missing)
print(f"\nMissing by variant:")
for v, count in sorted(variant_counts.items()):
    print(f"  {v}: {count}")
