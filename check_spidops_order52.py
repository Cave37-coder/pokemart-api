from orders.models import OrderItem

items = OrderItem.objects.filter(order_id=52, product_name__icontains="Spidops")

print(f"Found {items.count()} matching OrderItem(s) for order 52")
print("-" * 60)

for i in items:
    print(f"OrderItem id: {i.id}")
    print(f"  product_name (snapshot): {i.product_name}")
    print(f"  product_id (FK): {i.product_id}")
    print(f"  product (resolved): {i.product}")
    if i.product:
        p = i.product
        print(f"    -> card_set: {p.card_set}")
        print(f"    -> card_number: {p.card_number}")
        print(f"    -> variant_override: {p.variant_override}")
        print(f"    -> pb_id: {getattr(p, 'pb_id', 'N/A')}")
    print("-" * 60)
