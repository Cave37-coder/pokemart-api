import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import PokemonProduct

# Check first few cards of PFL and POR
for code in ["PFL", "POR", "MEG"]:
    print(f"\n{code} card #1:")
    cards = PokemonProduct.objects.filter(
        card_set__code=code, card_number=1
    ).values("name", "variant_override", "stock")
    for c in cards:
        print(f"  {c['variant_override']:5} {c['name']} stock={c['stock']}")
