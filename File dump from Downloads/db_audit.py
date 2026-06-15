"""
DB Audit — compare CSV bible vs DB for ASC, PRE, BLK, WHT
Run: python manage.py shell --command="exec(open('db_audit.py').read())"
"""
import csv
from collections import defaultdict
from products.models import PokemonProduct

target_sets = ['ASC', 'PRE', 'BLK', 'WHT']

# Load CSV bible
csv_data = defaultdict(list)  # set_code -> list of rows
with open('pokebulk_cards_20260524_1558.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        abbrev = row['abbreviation']
        if abbrev in target_sets and row['isCard'].strip().upper() == 'TRUE':
            csv_data[abbrev].append(row)

# Load DB records
db_data = defaultdict(list)  # set_code -> list of products
for abbrev in target_sets:
    products = PokemonProduct.objects.filter(
        card_set__code=abbrev
    ).values(
        'id', 'card_number', 'name', 'variant_override',
        'tcgcsv_product_id', 'price', 'pb_id'
    ).order_by('card_number', 'variant_override')
    db_data[abbrev] = list(products)

for abbrev in target_sets:
    csv_rows = csv_data[abbrev]
    db_rows = db_data[abbrev]

    print(f"\n{'='*70}")
    print(f"SET: {abbrev}")
    print(f"  CSV rows: {len(csv_rows)}")
    print(f"  DB rows:  {len(db_rows)}")

    # Build CSV lookup: (card_number, db_variant) -> row
    csv_lookup = {}
    for r in csv_rows:
        num = r['number'].split('/')[0].strip().zfill(3)
        variant = r['db_variant']
        key = (num, variant)
        csv_lookup[key] = r

    # Build DB lookup: (card_number_padded, variant) -> record
    db_lookup = {}
    for p in db_rows:
        num = str(p['card_number']).zfill(3)
        variant = p['variant_override'] or 'N'
        key = (num, variant)
        if key in db_lookup:
            # DUPLICATE
            db_lookup[key + ('DUP',)] = p
        else:
            db_lookup[key] = p

    # Find issues
    to_delete = []    # In DB but not in CSV
    to_update = []    # Wrong productId
    to_add = []       # In CSV but not in DB
    correct = []      # All good
    duplicates = []   # Multiple DB records for same key

    # Check for duplicates in DB
    seen_keys = defaultdict(list)
    for p in db_rows:
        num = str(p['card_number']).zfill(3)
        variant = p['variant_override'] or 'N'
        seen_keys[(num, variant)].append(p)

    for key, records in seen_keys.items():
        if len(records) > 1:
            duplicates.append((key, records))

    # Check each DB record against CSV
    checked_csv_keys = set()
    for p in db_rows:
        num = str(p['card_number']).zfill(3)
        variant = p['variant_override'] or 'N'
        key = (num, variant)

        if key in csv_lookup:
            csv_row = csv_lookup[key]
            csv_pid = int(csv_row['productId'])
            db_pid = p['tcgcsv_product_id']
            checked_csv_keys.add(key)

            if db_pid != csv_pid:
                to_update.append({
                    'id': p['id'],
                    'pb_id': p['pb_id'],
                    'card_number': num,
                    'variant': variant,
                    'db_pid': db_pid,
                    'csv_pid': csv_pid,
                    'name': p['name'],
                })
            else:
                correct.append(key)
        else:
            to_delete.append({
                'id': p['id'],
                'pb_id': p['pb_id'],
                'card_number': num,
                'variant': variant,
                'db_pid': p['tcgcsv_product_id'],
                'name': p['name'],
            })

    # Check CSV records not in DB
    for key, csv_row in csv_lookup.items():
        if key not in checked_csv_keys:
            to_add.append({
                'card_number': key[0],
                'variant': key[1],
                'csv_pid': csv_row['productId'],
                'name': csv_row['name'],
                'zar': csv_row['pokebulk_zar'],
            })

    print(f"\n  DUPLICATES in DB: {len(duplicates)}")
    for key, records in duplicates[:5]:
        print(f"    #{key[0]} {key[1]}: {len(records)} records — ids={[r['id'] for r in records]}")

    print(f"\n  TO DELETE (in DB, not in CSV): {len(to_delete)}")
    for r in to_delete[:10]:
        print(f"    id={r['id']} #{r['card_number']} {r['variant']:<10} pid={r['db_pid']} {r['name'][:30]}")

    print(f"\n  TO UPDATE (wrong productId): {len(to_update)}")
    for r in to_update[:10]:
        print(f"    id={r['id']} #{r['card_number']} {r['variant']:<10} db_pid={r['db_pid']} → csv_pid={r['csv_pid']} {r['name'][:25]}")

    print(f"\n  TO ADD (in CSV, not in DB): {len(to_add)}")
    for r in to_add[:10]:
        print(f"    #{r['card_number']} {r['variant']:<10} pid={r['csv_pid']} {r['name'][:30]} R{r['zar']}")

    print(f"\n  CORRECT (matching productId): {len(correct)}")
    print(f"\n  SUMMARY: {len(duplicates)} dupes | {len(to_delete)} delete | {len(to_update)} update | {len(to_add)} add | {len(correct)} correct")

