"""
Final fix for 34 ASC problem records.
- Rename BRH-PB to correct ball variant and fix productId
- Rename BRH-R to TRH and fix productId
- For N records that don't exist in CSV — update productId to correct N pid where available
Run: python manage.py shell --command="exec(open('fix_asc_final.py').read())"
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

# Explicit fix map: id -> (new_variant, new_pid_variant_key)
# For each problem record: what should the variant be? look up pid from CSV
FIXES = {
    # BRH-PB -> correct ball variant
    359515: ('BRH-FB',  '#030'),
    359494: ('BRH-QB',  '#028'),
    359359: ('BRH-FB',  '#052'),
    359353: ('BRH-DB',  '#045'),
    359321: ('BRH-DB',  '#044'),
    359248: ('BRH-QB',  '#065'),
    359242: ('BRH-QB',  '#062'),
    359238: ('BRH-FB',  '#056'),
    359169: ('BRH-QB',  '#017'),
    359162: ('BRH-QB',  '#067'),
    359156: ('BRH-FB',  '#037'),
    359153: ('BRH-QB',  '#064'),
    359148: ('BRH-FB',  '#021'),
    359138: ('BRH-QB',  '#060'),
    359133: ('BRH-FB',  '#041'),
    359118: ('BRH-LB',  '#039'),
    359094: ('BRH-QB',  '#034'),
    359091: ('BRH-QB',  '#063'),
    359070: ('BRH-FB',  '#029'),
    359037: ('BRH-LB',  '#046'),
    359031: ('BRH-FB',  '#016'),
    359019: ('BRH-FB',  '#036'),
    359009: ('BRH-QB',  '#059'),
    358996: ('BRH-QB',  '#027'),
    358990: ('BRH-FB',  '#055'),
    358985: ('BRH-FB',  '#054'),
    358977: ('BRH-QB',  '#066'),
    # BRH-R -> TRH
    359050: ('TRH',     '#019'),
    # N records that don't exist in CSV — update to correct N pid
    # #006 N — no N in CSV, card is Holofoil only. Keep as N, fix pid to H pid as placeholder
    # Actually check: card #006 = Erika's Victreebel, CSV has H/BRH-PB/ERH
    # The N variant doesn't exist — this stock needs manual decision
    # #019 N — CSV has H/TRH/ERH, no N
    359048: ('N',       '#019'),  # Will try to find N pid, else flag
    # #024 N — CSV has H/BRH-PB/ERH, no N. Ethan's Magcargo is a Rare/Holo
    359396: ('N',       '#024'),
    # #025 N — CSV has H/BRH-QB/ERH, no N. Entei is Rare
    359191: ('N',       '#025'),
    # #067 N — CSV has H/BRH-QB/ERH, no N. Tapu Koko is Rare
    359160: ('N',       '#067'),
    # #072 N — CSV has H/BRH-PB/ERH, no N. Iono's Kilowattrel
    359252: ('N',       '#072'),
    # #006 N — Erika's Victreebel
    359265: ('N',       '#006'),
}

records = list(PokemonProduct.objects.filter(id__in=list(FIXES.keys())).values(
    'id', 'card_number', 'variant_override', 'tcgcsv_product_id', 'stock', 'name', 'pb_id'
))

to_update = []
manual_review = []

for p in records:
    rec_id = p['id']
    if rec_id not in FIXES:
        continue

    new_variant, num_hint = FIXES[rec_id]
    num = str(p['card_number']).zfill(3)

    if new_variant in csv_by_num.get(num, {}):
        csv_entry = csv_by_num[num][new_variant]
        to_update.append({
            'id': rec_id,
            'num': num,
            'old_variant': p['variant_override'],
            'new_variant': new_variant,
            'old_pid': p['tcgcsv_product_id'],
            'new_pid': csv_entry['pid'],
            'new_zar': csv_entry['zar'],
            'stock': p['stock'],
            'name': p['name'],
            'new_pb_id': p['pb_id'].replace(p['variant_override'] or 'N', new_variant) if p['variant_override'] else p['pb_id'],
        })
    else:
        manual_review.append({
            'id': rec_id,
            'num': num,
            'variant': new_variant,
            'stock': p['stock'],
            'name': p['name'],
            'available': list(csv_by_num.get(num, {}).keys()),
        })

print(f"To update: {len(to_update)}")
print(f"Manual review: {len(manual_review)}")

print(f"\nUpdates:")
for u in to_update:
    print(f"  id={u['id']} #{u['num']} {u['old_variant']}->{u['new_variant']} pid={u['old_pid']}->{u['new_pid']} stock={u['stock']} {u['name'][:30]}")

print(f"\nManual review (no variant in CSV):")
for m in manual_review:
    print(f"  id={m['id']} #{m['num']} variant={m['variant']} stock={m['stock']} available={m['available']} {m['name'][:30]}")

# Apply updates
if to_update:
    objs = list(PokemonProduct.objects.filter(id__in=[u['id'] for u in to_update]))
    id_map = {u['id']: u for u in to_update}
    for obj in objs:
        u = id_map[obj.id]
        obj.variant_override = u['new_variant']
        obj.tcgcsv_product_id = u['new_pid']
        obj.pb_id = u['new_pb_id']
        if u['new_zar']:
            obj.price = u['new_zar']
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(
            objs, ['variant_override', 'tcgcsv_product_id', 'pb_id', 'price']
        )
    print(f"\nFixed {len(objs)} records")

print("\nDone.")
