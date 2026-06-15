"""
migrate_cart_items.py
Migrates cart items pointing at wrong-named records (ending in (Normal)/(Holofoil)/(Reverse Holo))
to the correct clean-named records, then verifies nothing is left pointing at bad records.
Run against Railway DB (DATABASE_URL uncommented in .env).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from orders.models import CartItem
from django.db import transaction

# Get all wrong-named product IDs
bad_products = PokemonProduct.objects.filter(
    name__regex=r'\((Normal|Holofoil|Reverse Holo)\)$'
).select_related('card_set')

bad_ids = set(bad_products.values_list('id', flat=True))
print(f"Wrong-named records in DB: {len(bad_ids)}")

# Get all cart items referencing bad records
bad_cart_items = CartItem.objects.filter(
    product_id__in=bad_ids
).select_related('product__card_set', 'cart__user')

print(f"Cart items to migrate: {bad_cart_items.count()}")
print()

migrated = 0
skipped = 0
errors = []

with transaction.atomic():
    for item in bad_cart_items:
        bad_product = item.product
        set_code = bad_product.card_set.code
        card_number = bad_product.card_number

        # Determine correct variant_sort from the bad name
        bad_name = bad_product.name
        if bad_name.endswith('(Reverse Holo)'):
            variant = 'RH'
        elif bad_name.endswith('(Holofoil)'):
            variant = 'H'
        else:
            variant = 'N'

        # Find the correct clean-named record
        # Match on same set, same card_number, same variant_sort, name does NOT end in bracketed variant
        candidates = PokemonProduct.objects.filter(
            card_set__code=set_code,
            card_number=card_number,
            variant_sort=variant,
        ).exclude(
            name__regex=r'\((Normal|Holofoil|Reverse Holo)\)$'
        )

        if candidates.count() == 0:
            errors.append(f"NO MATCH: {item.cart.user.username} | {set_code} #{card_number} {variant} | {bad_name}")
            skipped += 1
            continue

        if candidates.count() > 1:
            # Pick the one with most stock, or first
            correct = candidates.order_by('-stock').first()
        else:
            correct = candidates.first()

        # Check if this user already has the correct product in their cart
        existing = CartItem.objects.filter(
            cart=item.cart,
            product=correct
        ).exclude(id=item.id).first()

        if existing:
            # Merge quantities
            existing.quantity += item.quantity
            existing.save()
            item.delete()
            print(f"  MERGED: {item.cart.user.username} | {bad_name} -> {correct.name} (merged qty {item.quantity} into existing)")
        else:
            # Reassign item to correct product
            old_name = bad_name
            item.product = correct
            item.save()
            print(f"  OK: {item.cart.user.username} | {old_name} -> {correct.name}")

        migrated += 1

print()
print("=" * 60)
print(f"Migrated:  {migrated}")
print(f"Skipped:   {skipped} (no clean match found)")
print()

if errors:
    print("ERRORS (no clean match):")
    for e in errors:
        print(f"  {e}")
    print()

# Verify
remaining = CartItem.objects.filter(product_id__in=bad_ids).count()
print(f"Cart items still pointing at bad records: {remaining}")

if remaining == 0 and skipped == 0:
    print()
    print("ALL CLEAR — safe to run: python manage.py wipe_variant_name_records --confirm")
else:
    print()
    print("WARNING — some items could not be migrated. Review errors above before wiping.")
