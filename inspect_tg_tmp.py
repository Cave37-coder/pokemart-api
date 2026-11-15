import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet

TG_CODES = ['BRSTG', 'ASRTG', 'LORTG', 'SITTG', 'CRZGG']

for code in TG_CODES:
    try:
        cs = CardSet.objects.get(code=code)
    except CardSet.DoesNotExist:
        print(f"=== {code}: not found ===")
        continue
    products = list(PokemonProduct.objects.filter(card_set=cs, is_active=True).order_by('card_number').values('id', 'name', 'card_number', 'image_url'))
    print(f"=== {code} ({cs.name}) -- {len(products)} active products ===")
    for p in products[:15]:
        print(f"  #{p['card_number']} {p['name']!r} -> {p['image_url']}")
    print()
