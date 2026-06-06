"""
set_cart_stock.py
Runs against Railway DB (DATABASE_URL must be uncommented in .env).
Sets stock = max(existing_stock, qty_in_carts + 2) for every product
currently in a customer cart. Safe to re-run.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from orders.models import CartItem
from products.models import PokemonProduct
from django.db.models import Sum

print("Fetching cart quantities from Railway DB...")

# Get total quantity needed per product across all carts
cart_totals = (
    CartItem.objects
    .filter(product__isnull=False)
    .values('product__id', 'product__name', 'product__variant_sort',
            'product__card_set__code', 'product__card_number')
    .annotate(total_qty=Sum('quantity'))
    .order_by('product__card_set__code', 'product__card_number')
)

updated = 0
already_ok = 0
errors = 0

print(f"\n{'SET':<8} {'#':<6} {'VAR':<5} {'CART_QTY':<10} {'OLD_STOCK':<11} {'NEW_STOCK':<10} NAME")
print("-" * 90)

for row in cart_totals:
    product_id = row['product__id']
    cart_qty = row['total_qty']
    needed = cart_qty + 2  # always keep 2 buffer above what's in carts

    try:
        product = PokemonProduct.objects.get(id=product_id)
        old_stock = product.stock

        if old_stock >= needed:
            already_ok += 1
            continue  # already has enough stock

        product.stock = needed
        product.save(update_fields=['stock'])

        set_code = row['product__card_set__code'] or '?'
        card_num = row['product__card_number'] or '?'
        variant = row['product__variant_sort'] or '0'
        name = row['product__name'] or ''

        print(f"{set_code:<8} {str(card_num):<6} {str(variant):<5} {cart_qty:<10} {old_stock:<11} {needed:<10} {name[:40]}")
        updated += 1

    except PokemonProduct.DoesNotExist:
        print(f"  [MISSING] product id={product_id}")
        errors += 1
    except Exception as e:
        print(f"  [ERROR] product id={product_id}: {e}")
        errors += 1

print()
print("=" * 60)
print(f"Updated:     {updated} products")
print(f"Already OK:  {already_ok} products (stock was sufficient)")
print(f"Errors:      {errors}")
print(f"Total cart products: {updated + already_ok + errors}")
print()
print("Done. All cart products now have stock >= (cart qty + 2).")
