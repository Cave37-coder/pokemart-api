import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import PokemonProduct

updated = PokemonProduct.objects.filter(
    image_url__contains='res.cloudinary.com'
).update(image_url='', image_small_url='')

print(f'Done. Cleared {updated} DB records.')
