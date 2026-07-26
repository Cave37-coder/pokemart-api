from orders.models import OrderItem
from products.models import PokemonProduct

# ============================================================
# SET THIS TO False ONLY AFTER YOU'VE REVIEWED THE DRY RUN OUTPUT
# ============================================================
DRY_RUN = False
# ============================================================

ORDER_ITEM_ID = 636
CORRECT_PRODUCT_ID = 448082

print("=" * 70)
print(f"{'DRY RUN' if DRY_RUN else 'LIVE RUN'}: Relink OrderItem {ORDER_ITEM_ID}")
print("=" * 70)

item = OrderItem.objects.get(id=ORDER_ITEM_ID)
target = PokemonProduct.objects.get(id=CORRECT_PRODUCT_ID)

print(f"OrderItem id: {item.id}")
print(f"  order_id: {item.order_id}")
print(f"  product_name (snapshot): {item.product_name}")
print(f"  current product_id (FK): {item.product_id}  <-- should be None")
print()
print(f"Target product to link:")
print(f"  id: {target.id}")
print(f"  name: {target.name}")
print(f"  card_set: {target.card_set}")
print(f"  card_number: {target.card_number}")
print(f"  variant_override: {target.variant_override}")
print(f"  pb_id: {target.pb_id}")
print(f"  stock: {target.stock}")
print()

if item.product_id is not None:
    print("!! WARNING: OrderItem.product_id is NOT None. Refusing to overwrite.")
    print("!! Investigate manually before proceeding — this script expects a null FK.")
elif item.product_name.strip() != target.name.strip():
    print("!! WARNING: product_name snapshot does not exactly match target name.")
    print(f"!!   snapshot: {item.product_name!r}")
    print(f"!!   target:   {target.name!r}")
    print("!! Double check this is the right product before setting DRY_RUN = False.")
else:
    print("Name match confirmed. FK is null as expected.")
    if DRY_RUN:
        print()
        print(">>> DRY RUN: no changes made.")
        print(f">>> Would set OrderItem {item.id}.product_id = {target.id}")
    else:
        item.product = target
        item.save(update_fields=["product"])
        print()
        print(f">>> LIVE: OrderItem {item.id}.product_id set to {target.id} and saved.")

print("=" * 70)
