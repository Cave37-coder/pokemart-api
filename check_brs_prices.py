import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet

# Check BRS card 1 - should have clear N vs RH price difference
cs = CardSet.objects.get(code="BRS")
cards = PokemonProduct.objects.filter(card_set=cs, card_number=1)
for p in cards:
    print(f"  variant={p.variant_override}  price=R{p.price}  pid={p.tcgcsv_product_id}")
