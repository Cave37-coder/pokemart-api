"""
recreate_order_132.py

Manually recreates Deon Becker's lost order. His confirmation email (Order
#132 / INV 00000132, Cash on Collection, sent 2026-08-01 12:33) went out,
but the order was never actually committed to the DB -- the checkout view
used to send that email from inside the same DB transaction as the order,
before the view returned; something after the send threw (most likely lock
contention with the variant_sort bulk_update running against the same ASC
rows at the same time) and rolled the whole transaction back, taking the
order, stock decrement, and cart-clear with it. Already fixed going forward
in orders/views.py (transaction.on_commit). This script just makes Deon
whole for the one order that got caught by it.

Looks up every line item live (by set code + card_number + variant code),
checks current stock, and prints a full match report. Creates NOTHING
until APPLY = True -- and even then, refuses to create anything if any
line item failed to match or is out of stock, so you can fix problems
first rather than shipping a partial/wrong order.

Usage:
    python manage.py shell -c "exec(open('recreate_order_132.py').read())"
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from products.models import PokemonProduct
from orders.models import Order, OrderItem, OrderTracking

APPLY = False  # flip to True once the dry-run match report below looks right

CUSTOMER_EMAIL = "deon.becker1992@gmail.com"

VARIANT_LABEL_TO_CODE = {
    "Normal": "N",
    "Holo": "H",
    "Reverse Holo": "RH",
    "Reverse Holo (Energy Symbol)": "ESH",
    "Reverse Holo (Poke Ball)": "PB",
    "Reverse Holo (Friend Ball)": "FB",
    "Reverse Holo (Love Ball)": "LB",
    "Reverse Holo (Quick Ball)": "QB",
    "Reverse Holo (Dusk Ball)": "DB",
    "Reverse Holo (Master Ball)": "MB",
    "Trick or Trade": "TT",
}

# (set_code, card_number, variant_label, unit_price) -- transcribed straight
# from the confirmation email Deon received.
ITEMS = [
    ("ASC", 9,   "Reverse Holo (Energy Symbol)", "5.90"),
    ("ASC", 16,  "Reverse Holo (Friend Ball)",   "4.60"),
    ("ASC", 29,  "Reverse Holo (Energy Symbol)", "4.20"),
    ("ASC", 40,  "Reverse Holo (Love Ball)",     "4.80"),
    ("ASC", 44,  "Reverse Holo (Energy Symbol)", "4.10"),
    ("ASC", 53,  "Reverse Holo (Energy Symbol)", "5.00"),
    ("ASC", 59,  "Reverse Holo (Quick Ball)",    "4.60"),
    ("ASC", 59,  "Reverse Holo (Energy Symbol)", "4.20"),
    ("ASC", 63,  "Reverse Holo (Energy Symbol)", "4.20"),
    ("ASC", 65,  "Reverse Holo (Quick Ball)",    "3.90"),
    ("ASC", 66,  "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 67,  "Reverse Holo (Quick Ball)",    "4.80"),
    ("ASC", 72,  "Reverse Holo (Energy Symbol)", "5.50"),
    ("ASC", 81,  "Normal",                       "3.30"),
    ("ASC", 85,  "Normal",                       "3.30"),
    ("ASC", 90,  "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 92,  "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 96,  "Holo",                         "4.10"),
    ("ASC", 98,  "Reverse Holo (Energy Symbol)", "6.10"),
    ("ASC", 99,  "Holo",                         "4.40"),
    ("ASC", 104, "Reverse Holo (Quick Ball)",    "4.20"),
    ("ASC", 104, "Reverse Holo (Energy Symbol)", "4.40"),
    ("ASC", 127, "Reverse Holo (Energy Symbol)", "9.10"),
    ("ASC", 132, "Reverse Holo (Energy Symbol)", "7.30"),
    ("ASC", 133, "Reverse Holo (Poke Ball)",     "5.50"),
    ("ASC", 140, "Reverse Holo (Love Ball)",     "5.00"),
    ("ASC", 144, "Reverse Holo (Dusk Ball)",     "4.60"),
    ("ASC", 146, "Reverse Holo (Quick Ball)",    "4.20"),
    ("ASC", 150, "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 155, "Reverse Holo (Poke Ball)",     "7.30"),
    ("ASC", 156, "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 158, "Reverse Holo (Quick Ball)",    "4.60"),
    ("ASC", 158, "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 159, "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 159, "Reverse Holo (Quick Ball)",    "4.80"),
    ("ASC", 163, "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 163, "Reverse Holo (Poke Ball)",     "4.10"),
    ("ASC", 165, "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 168, "Reverse Holo (Energy Symbol)", "5.30"),
    ("ASC", 170, "Reverse Holo (Poke Ball)",     "4.40"),
    ("ASC", 177, "Reverse Holo (Energy Symbol)", "4.60"),
    ("ASC", 180, "Reverse Holo",                 "4.60"),
    ("ASC", 185, "Reverse Holo",                 "7.90"),
    ("ASC", 206, "Reverse Holo",                 "5.50"),
    ("ASC", 208, "Reverse Holo",                 "5.50"),
    ("ASR", 9,   "Normal",                       "2.80"),
    ("ASR", 90,  "Normal",                       "4.40"),
    ("JTG", 15,  "Normal",                       "2.80"),
    ("JTG", 130, "Normal",                       "3.00"),
    ("LOR", 142, "Normal",                       "5.10"),
    ("OBF", 21,  "Normal",                       "3.30"),
    ("PAL", 14,  "Normal",                       "3.50"),
    ("PAR", 138, "Normal",                       "2.80"),
    ("PRE", 33,  "Holo",                         "7.30"),
    ("MEW", 133, "Normal",                       "4.40"),
    ("SSP", 143, "Normal",                       "4.40"),
    ("SM9", 79,  "Normal",                       "5.10"),
    ("SM9", 80,  "Normal",                       "4.20"),
    ("TT24", 130, "Trick or Trade",              "9.00"),
    ("SM11", 157, "Normal",                      "4.60"),
]

print(f"Mode: {'APPLY (creating order)' if APPLY else 'DRY RUN (no changes will be saved)'}")
print(f"Looking up {len(ITEMS)} line items for {CUSTOMER_EMAIL}...\n")

User = get_user_model()
user = None
try:
    user = User.objects.get(email__iexact=CUSTOMER_EMAIL)
except User.DoesNotExist:
    print(f"NO ACCOUNT FOUND for {CUSTOMER_EMAIL} -- can't create the order without a user. Stopping.")
except User.MultipleObjectsReturned:
    print(f"MULTIPLE ACCOUNTS found for {CUSTOMER_EMAIL} -- resolve manually. Stopping.")

matched = []
problems = []

if user is not None:
    for set_code, card_number, variant_label, price_str in ITEMS:
        variant_code = VARIANT_LABEL_TO_CODE.get(variant_label)
        if variant_code is None:
            problems.append(f"  [{set_code} #{card_number}] Unknown variant label {variant_label!r} -- add it to VARIANT_LABEL_TO_CODE.")
            continue
        override = "" if variant_code == "N" else variant_code
        products = list(PokemonProduct.objects.filter(
            card_set__code=set_code,
            card_number=card_number,
            variant_override=override,
            is_active=True,
        ))
        if len(products) != 1:
            problems.append(
                f"  [{set_code} #{card_number}] variant={variant_label!r} ({variant_code or 'N'}) "
                f"-- found {len(products)} matching product(s), expected exactly 1."
            )
            continue
        p = products[0]
        if p.stock < 1:
            problems.append(f"  [{set_code} #{card_number}] {p.name} ({variant_code or 'N'}) -- OUT OF STOCK (stock={p.stock}).")
            continue
        matched.append((p, Decimal(price_str)))
        print(f"  OK  [{set_code} #{card_number}] {p.name} ({variant_code or 'N'}) -- stock={p.stock}, invoiced R{price_str}, current price R{p.price}")

    print(f"\nMatched {len(matched)}/{len(ITEMS)} items cleanly.")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S) -- resolve these before applying:")
        for prob in problems:
            print(prob)

    total = sum(price for _, price in matched)
    print(f"\nOrder total if created now: R{total:.2f} ({len(matched)} items, shipping R0 -- Cash on Collection)")

    if APPLY and not problems and matched:
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                total_price=total,
                status='pending',
                payment_method='coc',
                shipping_method='collection',
                shipping_cost=Decimal('0'),
                delivery_method='collection',
                customer_note='',
                internal_note=(
                    'Manually recreated -- original Order #132 / INV 00000132 (placed '
                    '2026-08-01 12:33) was lost when the confirmation email fired before '
                    'the DB transaction committed and a later step rolled everything back. '
                    'Fixed going forward in orders/views.py (transaction.on_commit).'
                ),
            )
            for product, price in matched:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    product_sku=product.csv_sku or '',
                    quantity=1,
                    price_at_purchase=price,
                )
                product.stock -= 1
                product.save()
            OrderTracking.objects.create(
                order=order,
                status=order.status,
                note='Order manually recreated after the original was lost to a checkout bug.',
            )
        print(f"\nDone. Created Order #{order.id} for {user.email} -- {len(matched)} items, R{total:.2f}.")
    elif APPLY:
        print("\nNOT applying -- there are unresolved problems above (or nothing matched). Fix them and re-run.")
    else:
        print("\nDry run only -- no order created. Re-run with APPLY = True once everything above looks right.")
