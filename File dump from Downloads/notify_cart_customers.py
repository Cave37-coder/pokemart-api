"""
notify_cart_customers.py
1. Generates a report of what sets affected customers were buying from
2. Sends a personalized email to each affected customer
Run with DATABASE_URL uncommented in .env
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from orders.models import Cart, CartItem
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from collections import defaultdict

User = get_user_model()

# ── Find affected customers (carts with null products) ──────────────────────
print("Finding affected customers...")
affected_carts = Cart.objects.prefetch_related('items').all()
affected = []
for cart in affected_carts:
    null_items = cart.items.filter(product__isnull=True).count()
    if null_items > 0:
        affected.append({
            'user': cart.user,
            'cart': cart,
            'null_items': null_items,
        })

print(f"Affected customers: {len(affected)}")
print()

# ── Known cart data from June 4 session (before wipe) ──────────────────────
# We recorded this earlier today
KNOWN_CARTS = {
    'Vogan':           {'items': 325, 'value': 1405},
    'StevoGpZa':       {'items': 188, 'value': 962},
    'alidax':          {'items': 97,  'value': 828},
    'Stefan':          {'items': 96,  'value': 297},
    'ankias_clefairy': {'items': 16,  'value': 115},
    'NIGHTWOLF':       {'items': 39,  'value': 69},
    'Landi':           {'items': 17,  'value': 29},
    'Antoinette':      {'items': 13,  'value': 40},
    'geoffbrown':      {'items': 9,   'value': 40},
    'TheShadowpuff':   {'items': 4,   'value': 17},
}

# ── Known set breakdown from dump earlier today ──────────────────────────────
SET_BREAKDOWN = {
    'SV1': 206, 'SV2': 120, 'ASC': 90, 'CRZ': 56, 'PRC': 43,
    'FCO': 40, 'BKP': 33, 'ROS': 30, 'BKT': 29, 'DRM': 25,
    'XY': 23, 'NXD': 21, 'PHF': 19, 'STS': 18, 'AOR': 14,
    'FLF': 13, 'EVO': 9, 'FFI': 7, 'KSS': 4, 'GEN': 3, 'BCR': 1,
}

# ── Print set priority report ────────────────────────────────────────────────
print("=" * 60)
print("SET PRIORITY REPORT — Stock these first!")
print("=" * 60)
print(f"{'SET':<8} {'CART ITEMS':<12} PRIORITY")
print("-" * 35)
for code, count in sorted(SET_BREAKDOWN.items(), key=lambda x: -x[1]):
    priority = "🔴 HIGH" if count >= 50 else "🟡 MED" if count >= 20 else "🟢 LOW"
    print(f"{code:<8} {count:<12} {priority}")

print()
print("=" * 60)
print("AFFECTED CUSTOMERS")
print("=" * 60)
for username, data in KNOWN_CARTS.items():
    try:
        user = User.objects.get(username=username)
        print(f"{username:<20} {data['items']:>4} items  ~R{data['value']:,}  {user.email}")
    except User.DoesNotExist:
        print(f"{username:<20} {data['items']:>4} items  ~R{data['value']:,}  (user not found)")

# ── Send emails ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("Sending emails...")
print("=" * 60)

EMAIL_SUBJECT = "Important notice about your PokéBulk SA Pile"
EMAIL_BODY = """Hi {name},

We're reaching out regarding your saved Pile on PokéBulk SA.

Due to a technical issue during a system upgrade today, the items in your saved Pile were unfortunately lost. We sincerely apologise for the inconvenience.

Your account, order history, and personal details are all completely safe and unaffected.

To help us prioritise which stock to make available first, could you reply to this email with a list of the sets or Pokémon you were looking for? We'll do our best to get those stocked as a priority.

In the meantime, all our cards are still available at www.pokebulk.co.za — you're welcome to re-add items to your Pile at any time.

Again, we're very sorry for this inconvenience.

Kind regards,
The PokéBulk SA Team
Tel: 074 488 6919
enquiries@pokebulk.co.za
www.pokebulk.co.za
"""

sent = 0
failed = 0
for username, data in KNOWN_CARTS.items():
    try:
        user = User.objects.get(username=username)
        if not user.email:
            print(f"  SKIP {username} — no email address")
            continue

        first_name = user.first_name or username
        body = EMAIL_BODY.format(name=first_name)

        try:
            send_mail(
                EMAIL_SUBJECT,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            print(f"  SENT → {username} ({user.email})")
            sent += 1
        except Exception as e:
            print(f"  FAILED → {username} ({user.email}): {e}")
            failed += 1

    except User.DoesNotExist:
        print(f"  SKIP {username} — user not found in DB")

print()
print(f"Emails sent: {sent}")
print(f"Emails failed: {failed}")
print()
print("Done.")
