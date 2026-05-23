import os, sys, django, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
sys.path.insert(0, '.')
django.setup()
from products.models import PokemonProduct

# Export by tcgcsv_product_id from local
data = {}
for p in PokemonProduct.objects.exclude(image_url='').exclude(image_url__isnull=True).exclude(tcgcsv_product_id__isnull=True):
    data[p.tcgcsv_product_id] = p.image_url

with open('image_urls_by_tcgid.json', 'w') as f:
    json.dump(data, f)
print(f'Exported {len(data)} image URLs by tcgcsv_product_id')
