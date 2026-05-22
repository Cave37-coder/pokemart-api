with open("orders/views.py", encoding="utf-8") as f:
    content = f.read()

old = "        order = Order.objects.create(\n            user=request.user,\n            total_price=total,\n            delivery_method=request.data.get('delivery_method', 'courier'),\n            delivery_address_line1=request.data.get('address_line1', ''),\n            delivery_address_line2=request.data.get('address_line2', ''),\n            delivery_city=request.data.get('city', ''),\n            delivery_province=request.data.get('province', ''),\n            delivery_postal_code=request.data.get('postal_code', ''),\n            customer_note=request.data.get('customer_note', ''),\n        )"

new = "        payment_method = request.data.get('payment_method', 'payfast')\n        shipping_method = request.data.get('shipping_method', 'pudo_locker')\n        is_eft = payment_method == 'eft'\n        is_coc = shipping_method == 'collection'\n\n        order = Order.objects.create(\n            user=request.user,\n            total_price=total,\n            status='pending_eft' if is_eft else 'pending',\n            payment_method='coc' if is_coc else payment_method,\n            shipping_method=shipping_method,\n            shipping_cost=request.data.get('shipping_cost', 0),\n            delivery_method='collection' if is_coc else 'courier',\n            delivery_address_line1=request.data.get('address_line1', ''),\n            delivery_address_line2=request.data.get('address_line2', ''),\n            delivery_city=request.data.get('city', ''),\n            delivery_province=request.data.get('province', ''),\n            delivery_postal_code=request.data.get('postal_code', ''),\n            pudo_locker_name=request.data.get('pudo_locker_name', ''),\n            pudo_locker_address=request.data.get('pudo_locker_address', ''),\n            customer_note=request.data.get('customer_note', ''),\n        )"

if old in content:
    content = content.replace(old, new)
    with open("orders/views.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Done - checkout view updated")
else:
    print("Pattern not found - showing current Order.objects.create block:")
    idx = content.find("Order.objects.create")
    print(repr(content[idx:idx+500]))
