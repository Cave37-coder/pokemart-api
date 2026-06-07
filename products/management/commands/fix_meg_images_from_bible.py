# fix_meg_images_from_bible.py
import os, django, csv
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from django.db import transaction

BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"
MEG_CODES = {"MEG", "PFL", "ASC", "POR", "CRI", "MEP", "MEE"}

print("Reading Bible CSV for MEG era image URLs...")
image_map = {}  # product_id -> bulbagarden image URL

with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        code = row.get('set_code', '').strip()
        if code not in MEG_CODES:
            continue
        pid = row.get('product_id', '').strip()
        img = row.get('final_image_url', '').strip()
        if pid and img and 'archives.bulbagarden.net' in img:
            image_map[int(pid)] = img

print(f"Found {len(image_map)} Bulbagarden image URLs")

# Update DB records
to_update = []
updated = 0

for code in MEG_CODES:
    records = PokemonProduct.objects.filter(
        card_set__code=code,
        tcgcsv_product_id__isnull=False
    )
    for p in records:
        img = image_map.get(p.tcgcsv_product_id)
        if img and img != p.image_url:
            p.image_url = img
            p.image_small_url = img
            to_update.append(p)
            updated += 1

print(f"Records to update: {updated}")

if to_update:
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(
            to_update, ['image_url', 'image_small_url'], batch_size=500
        )
    print("Done - images updated from Bulbagarden Archives")
