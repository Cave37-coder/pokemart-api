"""
Add missing ASC variants from CSV
Run: python manage.py shell --command="exec(open('fix_asc_missing_variants.py').read())"
"""
import csv
from products.models import PokemonProduct, CardSet, Category

RARITY_MAP = {
    "Common": "common", "Uncommon": "uncommon", "Rare": "rare",
    "Holo Rare": "holo_rare", "Rare Holo": "holo_rare",
    "Double Rare": "ultra_rare", "Ultra Rare": "ultra_rare",
    "Illustration Rare": "illustration_rare",
    "Special Illustration Rare": "special_illustration_rare",
    "Hyper Rare": "hyper_rare", "ACE SPEC Rare": "ultra_rare",
}

def parse_number(raw):
    import re
    if not raw:
        return None
    raw = str(raw).split('/')[0].strip()
    try:
        return int(raw)
    except ValueError:
        match = re.match(r'^[A-Za-z]+(\d+)$', raw)
        if match:
            return int(match.group(1))
        return None

VARIANT_SORT = {
    'N': 0, 'H': 1, 'RH': 2, 'ERH': 3,
    'BRH-PB': 4, 'BRH-FB': 4, 'BRH-QB': 4, 'BRH-LB': 4, 'BRH-DB': 4,
    'TRH': 4, 'RH-MB': 5,
}

csv_rows = []
with open('pokebulk_cards_20260524_1558.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['abbreviation'] == 'ASC' and row['isCard'].strip().upper() == 'TRUE':
            csv_rows.append(row)

db_records = set()
for p in PokemonProduct.objects.filter(card_set__code='ASC').values('card_number','variant_override'):
    db_records.add((str(p['card_number']).zfill(3), p['variant_override']))

card_set = CardSet.objects.get(code='ASC')
category, _ = Category.objects.get_or_create(name="Pokemon")

created = errors = 0
for row in csv_rows:
    num = row['number'].split('/')[0].strip().zfill(3)
    variant = row['db_variant']
    if (num, variant) in db_records:
        continue
    
    card_number = parse_number(row['number'])
    if card_number is None:
        continue
    
    zar = float(row['pokebulk_zar']) if row['pokebulk_zar'] else 1.50
    rarity = RARITY_MAP.get(row.get('rarity', ''), 'common')
    pb_id = f"ASC-{card_number}-{variant}"
    
    try:
        PokemonProduct.objects.create(
            pb_id=pb_id,
            tcgcsv_product_id=int(row['productId']) if row['productId'] else None,
            name=row['name'],
            card_number=card_number,
            card_set=card_set,
            category=category,
            variant_override=variant,
            variant_sort=VARIANT_SORT.get(variant, 9),
            rarity=rarity,
            price=zar,
            stock=0,
            is_active=True,
        )
        created += 1
    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  ERROR #{num} {variant}: {e}")

print(f"Created: {created} | Errors: {errors}")
