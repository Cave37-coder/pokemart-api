"""
DB Fix — ASC, PRE, BLK, WHT
Steps:
  1. Delete wrong records
  2. Update wrong productIds + prices
  3. Add missing records

Run: python manage.py shell --command="exec(open('db_fix.py').read())"
"""
import csv
from decimal import Decimal, ROUND_UP
import math
from collections import defaultdict
from django.db import transaction
from products.models import PokemonProduct, CardSet, Category, Era

target_sets = ['ASC', 'PRE', 'BLK', 'WHT']

MARKUP = Decimal("1.10")
MIN_ZAR = Decimal("1.50")

RARITY_MAP = {
    "Common": "common", "Uncommon": "uncommon", "Rare": "rare",
    "Holo Rare": "holo_rare", "Rare Holo": "holo_rare",
    "Double Rare": "ultra_rare", "Ultra Rare": "ultra_rare",
    "Illustration Rare": "illustration_rare",
    "Special Illustration Rare": "special_illustration_rare",
    "Hyper Rare": "hyper_rare", "Shiny Rare": "shiny_rare",
    "Shiny Ultra Rare": "shiny_ultra_rare", "Rare Secret": "secret_rare",
    "Rare Rainbow": "hyper_rare", "ACE SPEC Rare": "ultra_rare",
    "Trainer Gallery Rare Holo": "holo_rare",
    "Trainer Gallery Ultra Rare": "ultra_rare",
    "Trainer Gallery Secret Rare": "secret_rare",
}

def round_up_50c(val):
    v = max(MIN_ZAR, Decimal(str(val)))
    return Decimal(math.ceil(float(v) * 2)) / 2

def parse_number(raw):
    if not raw:
        return None
    raw = str(raw).split('/')[0].strip()
    try:
        return int(raw)
    except ValueError:
        return None

# Load CSV
print("Loading CSV bible...")
csv_data = defaultdict(list)
with open('pokebulk_cards_20260524_1558.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        abbrev = row['abbreviation']
        if abbrev in target_sets and row['isCard'].strip().upper() == 'TRUE':
            csv_data[abbrev].append(row)
print(f"  Loaded {sum(len(v) for v in csv_data.values())} CSV rows")

# Load DB
print("Loading DB records...")
db_data = defaultdict(list)
for abbrev in target_sets:
    db_data[abbrev] = list(
        PokemonProduct.objects.filter(card_set__code=abbrev)
        .values('id', 'card_number', 'name', 'variant_override',
                'tcgcsv_product_id', 'price', 'pb_id', 'stock')
    )
print(f"  Loaded {sum(len(v) for v in db_data.values())} DB records")

total_deleted = total_updated = total_added = total_errors = 0

for abbrev in target_sets:
    print(f"\n{'='*60}")
    print(f"Processing {abbrev}...")

    csv_rows = csv_data[abbrev]
    db_rows = db_data[abbrev]

    card_set = CardSet.objects.get(code=abbrev)
    category, _ = Category.objects.get_or_create(name="Pokemon")

    # Build CSV lookup: (card_number_padded, db_variant) -> row
    csv_lookup = {}
    for r in csv_rows:
        num = r['number'].split('/')[0].strip().zfill(3)
        variant = r['db_variant']
        key = (num, variant)
        csv_lookup[key] = r

    # Build DB lookup: (card_number_padded, variant) -> record
    db_lookup = {}
    seen_keys = defaultdict(list)
    for p in db_rows:
        num = str(p['card_number']).zfill(3)
        variant = p['variant_override'] or 'N'
        key = (num, variant)
        seen_keys[key].append(p)

    # Identify actions
    to_delete_ids = []
    to_update = []
    to_add = []
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

            # Calculate correct price
            zar = None
            if csv_row.get('pokebulk_zar'):
                try:
                    zar = float(csv_row['pokebulk_zar'])
                except:
                    pass

            if db_pid != csv_pid:
                to_update.append({
                    'id': p['id'],
                    'csv_pid': csv_pid,
                    'zar': zar,
                })
            elif zar and float(p['price']) != zar:
                # pid correct but price wrong — update price only
                to_update.append({
                    'id': p['id'],
                    'csv_pid': csv_pid,
                    'zar': zar,
                })
        else:
            to_delete_ids.append(p['id'])

    # Records in CSV but not in DB
    for key, csv_row in csv_lookup.items():
        if key not in checked_csv_keys:
            card_number = parse_number(csv_row['number'])
            if card_number is None:
                continue
            zar = None
            if csv_row.get('pokebulk_zar'):
                try:
                    zar = float(csv_row['pokebulk_zar'])
                except:
                    pass

            rarity = RARITY_MAP.get(csv_row.get('rarity', ''), 'common')
            variant = csv_row['db_variant']
            pb_id = f"{abbrev}-{card_number}-{variant}"

            to_add.append({
                'pb_id': pb_id,
                'tcgcsv_product_id': int(csv_row['productId']),
                'name': csv_row['name'],
                'card_number': card_number,
                'card_set': card_set,
                'category': category,
                'variant_override': variant,
                'rarity': rarity,
                'hp': csv_row.get('hp') or None,
                'artist': csv_row.get('artist') or '',
                'price': zar or 0,
                'stock': 0,
                'is_active': True,
            })

    print(f"  To delete: {len(to_delete_ids)}")
    print(f"  To update: {len(to_update)}")
    print(f"  To add:    {len(to_add)}")

    # STEP 1: DELETE
    with transaction.atomic():
        # Only delete records with 0 stock to be safe
        safe_delete = list(
            PokemonProduct.objects.filter(
                id__in=to_delete_ids, stock=0
            ).values_list('id', flat=True)
        )
        has_stock = len(to_delete_ids) - len(safe_delete)
        if has_stock:
            print(f"  WARNING: {has_stock} records have stock > 0 — skipping delete for those")

        deleted = PokemonProduct.objects.filter(id__in=safe_delete).delete()
        count_deleted = deleted[0]
        total_deleted += count_deleted
        print(f"  Deleted: {count_deleted}")

    # STEP 2: UPDATE
    update_objs = list(PokemonProduct.objects.filter(
        id__in=[u['id'] for u in to_update]
    ))
    id_to_update = {u['id']: u for u in to_update}
    for obj in update_objs:
        u = id_to_update[obj.id]
        obj.tcgcsv_product_id = u['csv_pid']
        if u['zar']:
            obj.price = u['zar']

    with transaction.atomic():
        PokemonProduct.objects.bulk_update(update_objs, ['tcgcsv_product_id', 'price'])
    total_updated += len(update_objs)
    print(f"  Updated: {len(update_objs)}")

    # STEP 3: ADD
    new_products = []
    for a in to_add:
        try:
            new_products.append(PokemonProduct(
                pb_id=a['pb_id'],
                tcgcsv_product_id=a['tcgcsv_product_id'],
                name=a['name'],
                card_number=a['card_number'],
                card_set=a['card_set'],
                category=a['category'],
                variant_override=a['variant_override'],
                rarity=a['rarity'],
                price=a['price'],
                stock=a['stock'],
                is_active=a['is_active'],
            ))
        except Exception as e:
            print(f"  ERROR building record: {e}")
            total_errors += 1

    with transaction.atomic():
        created = PokemonProduct.objects.bulk_create(
            new_products, ignore_conflicts=True
        )
    total_added += len(created)
    print(f"  Added: {len(created)}")

print(f"\n{'='*60}")
print(f"COMPLETE")
print(f"  Total deleted: {total_deleted}")
print(f"  Total updated: {total_updated}")
print(f"  Total added:   {total_added}")
print(f"  Total errors:  {total_errors}")
print(f"\nNOTE: Run enrich script on ASC, PRE, BLK, WHT after this")
print(f"      to populate images, types, attacks for new records.")
