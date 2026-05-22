import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet

# Check POP5 cards - what prices do they actually have in DB?
cs = CardSet.objects.get(code="POP5")
for p in PokemonProduct.objects.filter(card_set=cs).order_by("card_number", "variant_override")[:10]:
    print(f"  {p.card_number:4} {p.variant_override:6} price=R{p.price}  stock={p.stock}  active={p.is_active}  tcgid={p.tcgcsv_product_id}")
