import json, math, os, sys, django
from decimal import Decimal

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet

MARKUP = Decimal("1.10")
RATE = Decimal("16.49")

def to_zar(usd):
    return Decimal(math.ceil(float(Decimal(str(usd)) * RATE * MARKUP) * 2)) / 2

with open("tcgcsv_prices_full.json") as f:
    raw = json.load(f)

price_map = {}
for key, usd in raw.items():
    pid_str, subtype = key.split("|", 1)
    pid = int(pid_str)
    price_map.setdefault(pid, {})[subtype] = float(usd)

# Check Ho-Oh POP5
cs = CardSet.objects.get(code="POP5")
cards = PokemonProduct.objects.filter(card_set=cs, card_number=1)
for p in cards:
    pid = p.tcgcsv_product_id
    subtypes = price_map.get(pid, {})
    print(f"name={p.name} variant={p.variant_override} pid={pid} current_price=R{p.price}")
    print(f"  TCGCSV subtypes: {subtypes}")
    print()
