import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct, CardSet

for code in ["G1", "G2", "N4", "LTR", "AQ"]:
    try:
        cs = CardSet.objects.get(code=code)
    except:
        continue
    orphans = PokemonProduct.objects.filter(card_set=cs, tcgcsv_product_id__isnull=True, price=0)
    variants = orphans.values_list("variant_override", flat=True).distinct()
    print(f"{code} — {orphans.count()} orphans, variants: {sorted(set(variants))}")
    for p in orphans[:3]:
        print(f"  card_number={p.card_number}  variant={p.variant_override}  name={p.name[:50]}")
    print()
