import django, os, csv, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import PokemonProduct
from django.db import connection

BIBLE = r'C:\Users\texca\pokemart-api\pokebulk_bible_v5.csv'
updated = 0
skipped = 0

with open(BIBLE, encoding='utf-8', errors='replace') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        pid = row.get('product_id', '').strip()
        image_url = row.get('final_image_url', '').strip()
        if not pid or not image_url:
            skipped += 1
            continue
        for attempt in range(3):
            try:
                connection.ensure_connection()
                rows = PokemonProduct.objects.filter(
                    tcgcsv_product_id=int(float(pid)),
                    image_url=''
                ).update(image_url=image_url, image_small_url=image_url)
                updated += rows
                break
            except Exception as e:
                if attempt < 2:
                    connection.close()
                    time.sleep(2)
                else:
                    skipped += 1
        if i % 2000 == 0:
            print(f'Row {i} | Restored: {updated} | Skipped: {skipped}')

print(f'Done. Restored: {updated} | Skipped: {skipped}')
