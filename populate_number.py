import django, os, csv
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import PokemonProduct

BIBLE = r'C:\Users\texca\pokemart-api\pokebulk_bible_v5.csv'
updated = 0
skipped = 0
with open(BIBLE, encoding='utf-8', errors='replace') as f:
    reader = csv.DictReader(f)
    for row in reader:
        pid = row.get('product_id', '').strip()
        number = row.get('number', '').strip()
        if not pid or not number:
            skipped += 1
            continue
        try:
            rows = PokemonProduct.objects.filter(tcgcsv_product_id=int(float(pid))).update(number=number)
            updated += rows
        except (ValueError, TypeError):
            skipped += 1
print(f'Done. Updated: {updated} | Skipped: {skipped}')
