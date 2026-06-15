"""
Fix ASC records where multiple variants share the same productId
Cross-references CSV to find correct productId per variant
Run: python manage.py shell --command="exec(open('fix_asc_duplicates.py').read())"
"""
import csv
from collections import defaultdict
from django.db import transaction
from products.models import PokemonProduct

# Load CSV lookup: (card_number_padded, db_variant) -> productId
csv_lookup = {}
with open('pokebulk_cards_20260524_1558.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['abbreviation'] != 'ASC':
            continue
        if row['isCard'].strip().upper() != 'TRUE':
            continue
        num = row['number'].split('/')[0].strip().zfill(3)
        variant = row['db_variant']
        csv_lookup[(num, variant)] = {
            'pid': int(row['productId']),
            'zar': float(row['pokebulk_zar']) if row['pokebulk_zar'] else None,
        }

print(f"CSV lookup entries: {len(csv_lookup)}")

# Find all ASC records where productId is shared across variants
all_asc = list(PokemonProduct.objects.filter(card_set__code='ASC').values(
    'id', 'card_number', 'variant_override', 'tcgcsv_product_id', 'price', 'stock', 'name'
))

# Group by card_number to find duplicates
by_number = defaultdict(list)
for p in all_asc:
    by_number[p['card_number']].append(p)

wrong = []
correct = []
not_in_csv = []

for card_num, records in by_number.items():
    num_padded = str(card_num).zfill(3)
    
    # Check each record against CSV
    for p in records:
        variant = p['variant_override'] or 'N'
        key = (num_padded, variant)
        
        if key in csv_lookup:
            csv_pid = csv_lookup[key]['pid']
            csv_zar = csv_lookup[key]['zar']
            
            if p['tcgcsv_product_id'] != csv_pid:
                wrong.append({
                    'id': p['id'],
                    'card_number': num_padded,
                    'variant': variant,
                    'current_pid': p['tcgcsv_product_id'],
                    'correct_pid': csv_pid,
                    'correct_zar': csv_zar,
                    'stock': p['stock'],
                    'name': p['name'],
                })
            else:
                correct.append(key)
        else:
            not_in_csv.append({
                'id': p['id'],
                'card_number': num_padded,
                'variant': variant,
                'pid': p['tcgcsv_product_id'],
                'stock': p['stock'],
                'name': p['name'],
            })

print(f"\nWrong productId: {len(wrong)}")
print(f"Correct: {len(correct)}")
print(f"Not in CSV: {len(not_in_csv)}")

print(f"\nWrong records:")
for w in wrong:
    print(f"  id={w['id']} #{w['card_number']} {w['variant']:<10} stock={w['stock']} pid={w['current_pid']} -> {w['correct_pid']} {w['name'][:30]}")

print(f"\nNot in CSV (will be left as-is):")
for n in not_in_csv:
    print(f"  id={n['id']} #{n['card_number']} {n['variant']:<10} stock={n['stock']} pid={n['pid']} {n['name'][:30]}")

# Fix the wrong ones
if wrong:
    print(f"\nFixing {len(wrong)} records...")
    fix_objs = list(PokemonProduct.objects.filter(id__in=[w['id'] for w in wrong]))
    id_map = {w['id']: w for w in wrong}
    
    for obj in fix_objs:
        w = id_map[obj.id]
        obj.tcgcsv_product_id = w['correct_pid']
        if w['correct_zar']:
            obj.price = w['correct_zar']
    
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(fix_objs, ['tcgcsv_product_id', 'price'])
    print(f"Fixed {len(fix_objs)} records")
else:
    print("\nNo fixes needed!")
