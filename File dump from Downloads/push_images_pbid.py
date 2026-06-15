import os, sys, django, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DATABASE_URL'] = 'postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway'
sys.path.insert(0, '.')
django.setup()
from products.models import PokemonProduct
from django.db import transaction

with open('image_urls_by_pbid.json') as f:
    data = json.load(f)

print(f'Loaded {len(data)} image URLs')
to_update = []
found = 0
for p in PokemonProduct.objects.all().iterator(chunk_size=2000):
    url = data.get(p.pb_id)
    if url:
        p.image_url = url
        to_update.append(p)
        found += 1
    if len(to_update) >= 2000:
        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, ['image_url'])
        print(f'  ...wrote {found}')
        to_update = []

if to_update:
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(to_update, ['image_url'])

print(f'Done. Updated {found} records on Railway')
