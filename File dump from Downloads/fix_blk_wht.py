"""
Re-add missing variants for BLK and WHT using individual saves
Run: python manage.py shell --command="exec(open('fix_blk_wht.py').read())"
"""
import csv
from decimal import Decimal
from products.models import PokemonProduct, CardSet, Category

RARITY_MAP = {
    "Common": "common", "Uncommon": "uncommon", "Rare": "rare",
    "Holo Rare": "holo_rare", "Rare Holo": "holo_rare",
    "Double Rare": "ultra_rare", "Ultra Rare": "ultra_rare",
    "Illustration Rare": "illustration_rare",
    "Special Illustration Rare": "special_illustration_rare",
    "Hyper Rare": "hyper_rare", "Shiny Rare": "shiny_rare",
    "Shiny Ultra Rare": "shiny_ultra_rare", "Rare Secret": "secret_rare",
    "Rare Rainbow": "hyper_rare", "ACE SPEC Rare": "ultra_rare",
}

def parse_number(raw):
    if not raw:
        return None
    raw = str(raw).split('/')[0].strip()
    try:
        return int(raw)
    except ValueError:
        import re
        match = re.match(r'^[A-Za-z]+(\d+)$', raw)
        if match:
            return int(match.group(1))
        return None

# Load CSV
csv_data = {'BLK': [], 'WHT': []}
with open('pokebulk_cards_20260524_1558.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['abbreviation'] in csv_data and row['isCard'].strip().upper() == 'TRUE':
            csv_data[row['abbreviation']].append(row)

category, _ = Category.objects.get_or_create(name="Pokemon")

for abbrev in ['BLK', 'WHT']:
    card_set = CardSet.objects.get(code=abbrev)
    csv_rows = csv_data[abbrev]

    # Get existing (card_number, variant) combos
    existing = set(
        PokemonProduct.objects.filter(card_set__code=abbrev)
        .values_list('card_number', 'variant_override')
    )

    created = skipped = errors = 0

    for row in csv_rows:
        card_number = parse_number(row['number'])
        if card_number is None:
            continue
        variant = row['db_variant']

        if (card_number, variant) in existing:
            skipped += 1
            continue

        zar = float(row['pokebulk_zar']) if row['pokebulk_zar'] else 1.50
        rarity = RARITY_MAP.get(row.get('rarity', ''), 'common')
        pb_id = f"{abbrev}-{card_number}-{variant}"

        try:
            PokemonProduct.objects.create(
                pb_id=pb_id,
                tcgcsv_product_id=int(row['productId']) if row['productId'] else None,
                name=row['name'],
                card_number=card_number,
                card_set=card_set,
                category=category,
                variant_override=variant,
                rarity=rarity,
                price=zar,
                stock=0,
                is_active=True,
            )
            created += 1
        except Exception as e:
            errors += 1

    print(f"{abbrev}: created={created} skipped={skipped} errors={errors}")

print("\nDone! Now run: python manage.py enrich_only BLK && python manage.py enrich_only WHT")
