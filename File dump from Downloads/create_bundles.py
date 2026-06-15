from products.models import Category, CardSet, PokemonProduct
import uuid

# 1. Get or create Bundles category
bundle_cat, created = Category.objects.get_or_create(
    name='Bundles',
    defaults={'slug': 'bundles'}
)
print(f"Category: {'Created' if created else 'Already exists'} — {bundle_cat}")

# 2. Get all sets that have cards
sets = CardSet.objects.filter(products__isnull=False).distinct().order_by('era__code', 'release_date')
print(f"Sets with cards: {sets.count()}")

created_count = 0
skipped_count = 0

for card_set in sets:
    existing = PokemonProduct.objects.filter(category=bundle_cat, card_set=card_set).exists()
    if existing:
        skipped_count += 1
        continue

    image_url = card_set.logo_url or card_set.symbol_url or ''
    image_small = card_set.symbol_url or ''
    bundle_name = f"{card_set.name} Complete Bundle"
    unique_pb_id = f"BUNDLE-{card_set.code}-{uuid.uuid4().hex[:6].upper()}"

    product = PokemonProduct(
        name=bundle_name,
        category=bundle_cat,
        card_set=card_set,
        price=0.00,
        stock=0,
        is_active=False,
        image_url=image_url,
        image_small_url=image_small,
        rarity='common',
        variant_override='BUNDLE',
        description=f'Complete {card_set.name} bundle. Set price and stock before activating.',
        pb_id=unique_pb_id,
    )
    product.save()
    created_count += 1
    print(f"  Created: {bundle_name}")

print(f"\nDone! Created: {created_count} | Skipped: {skipped_count}")
print(f"Go to admin > Products > filter Category=Bundles to set prices.")
