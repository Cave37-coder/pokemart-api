import os, sys, django, csv
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct

orphans = PokemonProduct.objects.filter(price=0).select_related("card_set__era").order_by("card_set__code", "card_number", "variant_override")

with open("manual_prices.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "set", "card_number", "variant", "name", "price_zar"])
    for p in orphans:
        w.writerow([p.id, p.card_set.code, p.card_number, p.variant_override, p.name, ""])

print(f"Exported {orphans.count()} cards to manual_prices.csv")
print("Fill in the price_zar column, then run import_manual_prices.py")
