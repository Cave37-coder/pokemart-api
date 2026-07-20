"""
Finds exactly which products are falling into sync_prices_only.py's
"no match" bucket, and cross-references against suspiciously-low prices
to quantify real financial exposure -- not just count the problem, show
which actual cards are affected.

Usage: python manage.py shell < diagnose_price_sync_gap.py
(or paste directly into `python manage.py shell`)
"""
from decimal import Decimal
from products.models import PokemonProduct

total = PokemonProduct.objects.filter(is_active=True).count()
unlinked = PokemonProduct.objects.filter(is_active=True, tcgcsv_product_id__isnull=True).count()

print(f"Total active products: {total:,}")
print(f"Missing tcgcsv_product_id (structurally invisible to nightly sync): {unlinked:,}\n")

# The real financial exposure: products stuck at exactly R1.50 (the
# known floor value) that ALSO have no way to ever be corrected.
stuck_at_floor = PokemonProduct.objects.filter(
    is_active=True,
    tcgcsv_product_id__isnull=True,
    price=Decimal("1.50"),
).select_related("card_set")

print(f"Stuck at R1.50 floor AND unreachable by nightly sync: {stuck_at_floor.count():,}\n")

print("=== Sample of 30 affected cards (name, set, current stuck price) ===")
for p in stuck_at_floor.select_related("card_set")[:30]:
    set_name = p.card_set.name if p.card_set else "?"
    print(f"  {p.name} [{set_name}] #{p.card_number or '?'} -- R{p.price} (variant: {p.variant_override or 'N'})")

# Broader check: unlinked products at ANY suspiciously low price, not
# just exactly R1.50 -- catches cases where the floor logic differed
# or the price was set some other way.
print("\n=== Unlinked products under R5, any price (broader net) ===")
low_unlinked = PokemonProduct.objects.filter(
    is_active=True,
    tcgcsv_product_id__isnull=True,
    price__lt=Decimal("5.00"),
).select_related("card_set").order_by("-price")

print(f"Count: {low_unlinked.count():,}\n")
for p in low_unlinked[:30]:
    set_name = p.card_set.name if p.card_set else "?"
    print(f"  {p.name} [{set_name}] #{p.card_number or '?'} -- R{p.price} (variant: {p.variant_override or 'N'})")
