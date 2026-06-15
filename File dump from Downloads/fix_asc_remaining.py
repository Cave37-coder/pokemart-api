"""
Fix the 34 ASC records that have ERH productIds but wrong variant codes.
Each needs its productId corrected to match its variant.
Run: python manage.py shell --command="exec(open('fix_asc_remaining.py').read())"
"""
import csv
from collections import defaultdict
from django.db import transaction
from products.models import PokemonProduct

# Load CSV: number -> variant -> {pid, zar}
csv_by_num = defaultdict(dict)
with open('pokebulk_cards_20260524_1558.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['abbreviation'] != 'ASC':
            continue
        if row['isCard'].strip().upper() != 'TRUE':
            continue
        num = row['number'].split('/')[0].strip().zfill(3)
        variant = row['db_variant']
        csv_by_num[num][variant] = {
            'pid': int(row['productId']),
            'zar': float(row['pokebulk_zar']) if row['pokebulk_zar'] else None,
            'name': row['name'],
        }

# The 34 problem record IDs and their current state
problem_ids = [
    359515, 359494, 359396, 359359, 359353, 359321, 359265, 359252,
    359248, 359242, 359238, 359191, 359169, 359162, 359160, 359156,
    359153, 359148, 359138, 359133, 359118, 359094, 359091, 359070,
    359050, 359048, 359037, 359031, 359019, 359009, 358996, 358990,
    358985, 358977
]

records = list(PokemonProduct.objects.filter(id__in=problem_ids).values(
    'id', 'card_number', 'variant_override', 'tcgcsv_product_id', 'stock', 'name'
))

to_fix = []
to_delete = []
no_match = []

for p in records:
    num = str(p['card_number']).zfill(3)
    variant = p['variant_override'] or 'N'

    if num in csv_by_num and variant in csv_by_num[num]:
        # Correct productId exists for this variant
        csv_entry = csv_by_num[num][variant]
        to_fix.append({
            'id': p['id'],
            'num': num,
            'variant': variant,
            'current_pid': p['tcgcsv_product_id'],
            'correct_pid': csv_entry['pid'],
            'correct_zar': csv_entry['zar'],
            'stock': p['stock'],
            'name': p['name'],
        })
    else:
        # Variant doesn't exist in CSV for this card
        # Check if it's a variant that simply doesn't exist (e.g. BRH-R on a card that only has ERH)
        available = list(csv_by_num.get(num, {}).keys())
        if p['stock'] == 0:
            to_delete.append({
                'id': p['id'],
                'num': num,
                'variant': variant,
                'pid': p['tcgcsv_product_id'],
                'name': p['name'],
                'available_variants': available,
            })
        else:
            no_match.append({
                'id': p['id'],
                'num': num,
                'variant': variant,
                'pid': p['tcgcsv_product_id'],
                'stock': p['stock'],
                'name': p['name'],
                'available_variants': available,
            })

print(f"To fix:   {len(to_fix)}")
print(f"To delete (no stock): {len(to_delete)}")
print(f"No match (has stock): {len(no_match)}")

print(f"\nFixes:")
for f in to_fix:
    print(f"  id={f['id']} #{f['num']} {f['variant']:<10} stock={f['stock']} pid={f['current_pid']} -> {f['correct_pid']} {f['name'][:30]}")

print(f"\nTo delete:")
for d in to_delete:
    print(f"  id={d['id']} #{d['num']} {d['variant']:<10} pid={d['pid']} available={d['available_variants']} {d['name'][:25]}")

print(f"\nNo match (manual review needed):")
for n in no_match:
    print(f"  id={n['id']} #{n['num']} {n['variant']:<10} stock={n['stock']} pid={n['pid']} available={n['available_variants']} {n['name'][:25]}")

# Apply fixes
if to_fix:
    fix_objs = list(PokemonProduct.objects.filter(id__in=[f['id'] for f in to_fix]))
    id_map = {f['id']: f for f in to_fix}
    for obj in fix_objs:
        f = id_map[obj.id]
        obj.tcgcsv_product_id = f['correct_pid']
        if f['correct_zar']:
            obj.price = f['correct_zar']
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(fix_objs, ['tcgcsv_product_id', 'price'])
    print(f"\nFixed {len(fix_objs)} records")

if to_delete:
    del_ids = [d['id'] for d in to_delete]
    with transaction.atomic():
        PokemonProduct.objects.filter(id__in=del_ids).delete()
    print(f"Deleted {len(to_delete)} records")

print("\nDone.")
