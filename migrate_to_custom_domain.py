import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct

OLD_DOMAIN = 'https://pub-77a8c30ac1fc4f4fbe1f2a7a0f15f174.r2.dev'
NEW_DOMAIN = 'https://images.pokebulk.co.za'

qs = PokemonProduct.objects.filter(image_url__contains='r2.dev')
total = qs.count()
print(f'Migrating {total} products from old r2.dev domain to custom domain...')

updated = 0
batch = []

for p in qs.iterator():
    if p.image_url:
        p.image_url = p.image_url.replace(OLD_DOMAIN, NEW_DOMAIN)
    if p.image_small_url:
        p.image_small_url = p.image_small_url.replace(OLD_DOMAIN, NEW_DOMAIN)
    batch.append(p)
    updated += 1

    if len(batch) >= 500:
        PokemonProduct.objects.bulk_update(batch, ['image_url', 'image_small_url'], batch_size=500)
        print(f'Progress: {updated}/{total}')
        batch = []

if batch:
    PokemonProduct.objects.bulk_update(batch, ['image_url', 'image_small_url'], batch_size=500)

print(f'DONE — {updated} products migrated to custom domain')
