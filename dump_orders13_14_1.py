import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from orders.models import Order

for oid in [13, 14]:
    try:
        o = Order.objects.get(id=oid)
    except:
        print(f'Order {oid} not found')
        continue

    u = o.user
    print('=' * 70)
    print(f'ORDER #{o.id} | {o.created_at} | Status: {o.status}')
    print(f'User:     {u.username}')
    print(f'Name:     {u.first_name} {u.last_name}')
    print(f'Email:    {u.email}')
    try:
        print(f'Phone:    {u.phone_number}')
    except:
        pass
    print(f'Delivery: {o.delivery_method}')
    for f in ['delivery_address_line1','delivery_address_line2','delivery_city','delivery_province','delivery_postal_code']:
        v = getattr(o, f, '')
        if v:
            print(f'  {f}: {v}')
    print(f'Note:     {o.customer_note}')
    print(f'Total:    R{o.total_price} | Shipping: R{o.shipping_cost}')
    print()
    print('ITEMS:')
    print(f"  {'#':<4} {'product_id':<12} {'price':<10} {'name':<30} {'sku'}")
    for i, item in enumerate(o.items.all(), 1):
        print(f"  {i:<4} {str(item.product_id):<12} R{item.price_at_purchase:<9.2f} {repr(item.product_name):<30} {repr(item.product_sku)}")
    print()
