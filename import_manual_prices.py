import os, sys, django, csv
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db import transaction
from decimal import Decimal

updated = 0
skipped = 0

with open("manual_prices.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    to_update = []
    for row in reader:
        price_raw = row.get("price_zar", "").strip()
        if not price_raw:
            skipped += 1
            continue
        try:
            price = Decimal(price_raw)
            p = PokemonProduct.objects.get(id=int(row["id"]))
            p.price = price
            p.is_active = True
            to_update.append(p)
            updated += 1
        except Exception as e:
            print(f"  Error row {row['id']}: {e}")

    with transaction.atomic():
        PokemonProduct.objects.bulk_update(to_update, ["price", "is_active"])

print(f"Done. Updated={updated}  Skipped(blank)={skipped}")
