"""
Fix 6 ASC records where N variant doesn't exist — convert to H
Run: python manage.py shell --command="exec(open('fix_asc_holo_only.py').read())"
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
        }

# The 6 records to convert N -> H
fix_ids = [359396, 359265, 359252, 359191, 359160, 359048]

records = list(PokemonProduct.objects.filter(id__in=fix_ids))

print(f"Converting {len(records)} N -> H records:")
for obj in records:
    num = str(obj.card_number).zfill(3)
    h_entry = csv_by_num.get(num, {}).get('H')
    if not h_entry:
        print(f"  WARNING: No H entry in CSV for #{num} {obj.name}")
        continue

    old_variant = obj.variant_override
    old_pid = obj.tcgcsv_product_id
    old_pb_id = obj.pb_id

    obj.variant_override = 'H'
    obj.tcgcsv_product_id = h_entry['pid']
    obj.pb_id = old_pb_id.replace(f"-{old_variant}", '-H') if old_variant else old_pb_id
    if h_entry['zar']:
        obj.price = h_entry['zar']

    print(f"  #{num} {old_variant}->H  pid={old_pid}->{h_entry['pid']}  stock={obj.stock}  price=R{obj.price}  {obj.name[:30]}")

with transaction.atomic():
    PokemonProduct.objects.bulk_update(
        records, ['variant_override', 'tcgcsv_product_id', 'pb_id', 'price']
    )

print(f"\nDone. Converted {len(records)} records to H variant.")
