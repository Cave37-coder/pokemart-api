import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from orders.models import CartItem
from django.db.models import Sum

items = CartItem.objects.select_related(
    'product__card_set'
).values(
    'product__card_set__code',
    'product__id',
    'product__name',
    'product__card_number',
    'product__variant_sort'
).annotate(
    total_qty=Sum('quantity')
).order_by('product__card_set__code', 'product__card_number')

lines = []
for i in items:
    line = "{}|{}|{}|{}|{}".format(
        i['product__card_set__code'],
        i['product__card_number'],
        i['product__variant_sort'],
        i['total_qty'],
        i['product__name']
    )
    lines.append(line)
    print(line)

with open('cart_stock_needed.txt', 'w') as f:
    f.write('\n'.join(lines))

print(f"\nTotal: {len(lines)} products need stock")
print("Saved to cart_stock_needed.txt")
