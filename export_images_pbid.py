import os, sys, django, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
sys.path.insert(0, '.')
django.setup()
from products.models import PokemonProduct

# Export by pb_id from local
data = {}
for p in PokemonProduct.objects.exclude(image_url='').exclude(image_url__isnull=True):
    if p.pb_id:
        data[p.pb_id] = p.image_url

with open('image_urls_by_pbid.json', 'w') as f:
    json.dump(data, f)
print(f'Exported {len(data)} image URLs by pb_id')
