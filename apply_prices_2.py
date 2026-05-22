"""
apply_prices.py
===============
PokéBulk SA — Direct price update from local tcgcsv_prices.json

Dead simple:
  1. Load tcgcsv_prices.json (productId -> USD price)
  2. Load all DB records that have tcgcsv_product_id set
  3. Match by productId, convert USD -> ZAR, update price
  4. Done. No name matching. No group lookup. No API calls.

Usage:
  python apply_prices.py              # live run
  python apply_prices.py --dry-run    # show counts only
  python apply_prices.py --rate 18.50 # override exchange rate
"""

import json, math, sys, os, django
from decimal import Decimal

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db import transaction

# ── Config ───────────────────────────────────────────────────────────────
MARKUP   = Decimal("1.10")
DRY_RUN  = "--dry-run" in sys.argv

# Rate: use --rate 18.50 to override
RATE = Decimal("16.49")
for arg in sys.argv:
    if arg.startswith("--rate="):
        RATE = Decimal(arg.split("=")[1])
    elif arg == "--rate" and sys.argv.index(arg) + 1 < len(sys.argv):
        RATE = Decimal(sys.argv[sys.argv.index(arg) + 1])

def round_up_50c(zar):
    return Decimal(math.ceil(float(zar) * 2)) / 2

def to_zar(usd):
    if not usd or float(usd) <= 0:
        return None
    return round_up_50c(Decimal(str(usd)) * RATE * MARKUP)

# ── Load prices ───────────────────────────────────────────────────────────
if not os.path.exists("tcgcsv_prices.json"):
    print("ERROR: tcgcsv_prices.json not found. Run fetch_prices.py first.")
    sys.exit(1)

print("Loading tcgcsv_prices.json...")
with open("tcgcsv_prices.json") as f:
    prices = json.load(f)

# Keys may be strings or ints depending on how they were saved
price_by_pid = {int(k): float(v) for k, v in prices.items() if v and float(v) > 0}
print(f"  {len(price_by_pid):,} products with prices loaded")
print(f"  Rate: 1 USD = R{RATE}  Markup: {MARKUP}x")
if DRY_RUN:
    print("  DRY RUN — no writes\n")
else:
    print()

# ── Load DB records with tcgcsv_product_id ────────────────────────────────
print("Loading DB records with tcgcsv_product_id...")
qs = PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True)
total_db = qs.count()
print(f"  {total_db:,} records have tcgcsv_product_id set\n")

# ── Match and update ──────────────────────────────────────────────────────
updated   = 0
skipped   = 0
no_price  = 0
to_update = []

print("Matching prices...")
for p in qs.iterator(chunk_size=2000):
    pid = p.tcgcsv_product_id
    usd = price_by_pid.get(pid)

    if usd is None:
        no_price += 1
        continue

    new_price = to_zar(usd)
    if new_price is None:
        no_price += 1
        continue

    if p.price == new_price:
        skipped += 1
        continue

    p.price = new_price
    # Also activate if price > 0 and currently inactive
    if new_price > 0 and not p.is_active:
        p.is_active = True

    to_update.append(p)
    updated += 1

    # Batch write every 2000
    if len(to_update) >= 2000 and not DRY_RUN:
        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, ["price", "is_active"])
        print(f"  ... wrote {updated:,} so far")
        to_update = []

# Final batch
if to_update and not DRY_RUN:
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(to_update, ["price", "is_active"])

# ── Summary ───────────────────────────────────────────────────────────────
print()
print("=" * 50)
print(f"DONE")
print(f"  Updated:          {updated:,}")
print(f"  Already correct:  {skipped:,}")
print(f"  No price in TCGCSV: {no_price:,}")
print(f"  Total processed:  {total_db:,}")
if DRY_RUN:
    print("\nDry run — nothing written to DB")
else:
    print(f"\nAll priced cards are now active.")
    print(f"Cards with no TCGCSV price remain inactive (price=0).")
