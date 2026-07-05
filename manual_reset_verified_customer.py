"""
manual_reset_verified_customer.py

For a customer whose identity is already confirmed (existing account +
order history) but who can't receive password reset emails. Sets a
temporary password directly so she can log in and place her second order,
without waiting on the SMTP issue to be fixed.

Usage:
    python manage.py shell -c "exec(open('manual_reset_verified_customer.py').read())"

DRY RUN by default -- shows the account and confirms it's the right one,
changes nothing. Set APPLY = True below to actually set the new password.
"""

import secrets
import string
from django.contrib.auth import get_user_model

User = get_user_model()

APPLY = False  # flip to True once you've confirmed this is the right account below

LOOKUP_EMAIL = "foxyinkzart247@gmail.com"
LOOKUP_USERNAME = "Lexi"

def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

user = User.objects.filter(email__iexact=LOOKUP_EMAIL).first() or \
       User.objects.filter(username__iexact=LOOKUP_USERNAME).first()

if not user:
    print(f"No account found for email={LOOKUP_EMAIL!r} or username={LOOKUP_USERNAME!r}.")
    print("Nothing to do -- double check the diagnostic script output before proceeding.")
else:
    print(f"Account found: username={user.username!r} email={user.email!r} "
          f"is_active={user.is_active} date_joined={user.date_joined}")

    # Show her order history so you can visually confirm this is really her
    # before applying anything (adjust related_name if your Order model differs).
    try:
        orders = user.orders.all()
        print(f"Orders on this account: {orders.count()}")
        for o in orders[:5]:
            print(f"  Order #{o.id} - {getattr(o, 'status', '?')} - {getattr(o, 'created_at', '?')}")
    except Exception as e:
        print(f"(Could not list orders automatically: {e}. Check the admin panel manually.)")

    if APPLY:
        temp_password = generate_temp_password()
        user.set_password(temp_password)
        user.save()
        print()
        print("=" * 50)
        print(f"Password updated. Temporary password: {temp_password}")
        print("=" * 50)
        print("Send this to her directly (phone/WhatsApp is safer than email, "
              "since email is the thing that's currently broken for her). "
              "Tell her to log in and change it immediately from her profile page.")
    else:
        print()
        print("DRY RUN -- no password changed. Confirm the account and order history "
              "above are really hers, then set APPLY = True and re-run.")
