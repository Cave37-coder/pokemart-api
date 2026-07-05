"""
diagnose_password_reset.py

Read-only diagnostic for a customer reporting "forgot password" emails
never arriving. Checks account existence, then does a live SMTP send
test so you can see exactly where the failure is -- account lookup,
or the email pipeline itself.

Usage:
    python manage.py shell -c "exec(open('diagnose_password_reset.py').read())"

Makes NO changes to any account. Safe to run anytime.
"""

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()

CHECK_EMAIL = "foxyinkzart247@gmail.com"
CHECK_USERNAME = "Lexi"

print("=" * 60)
print("STEP 1: Account lookup")
print("=" * 60)

by_email = User.objects.filter(email__iexact=CHECK_EMAIL)
by_username = User.objects.filter(username__iexact=CHECK_USERNAME)

if by_email.exists():
    for u in by_email:
        print(f"  Found by email: username={u.username!r} email={u.email!r} "
              f"is_active={u.is_active} date_joined={u.date_joined}")
else:
    print(f"  No account found with email={CHECK_EMAIL!r}")

if by_username.exists():
    for u in by_username:
        print(f"  Found by username: username={u.username!r} email={u.email!r} "
              f"is_active={u.is_active} date_joined={u.date_joined}")
else:
    print(f"  No account found with username={CHECK_USERNAME!r}")

if by_email.exists() and by_username.exists() and by_email.first().pk != by_username.first().pk:
    print("  WARNING: email and username belong to TWO DIFFERENT accounts. "
          "Confirm which one she's actually trying to access before doing anything else.")

if not by_email.exists() and not by_username.exists():
    print("  NOTE: Neither the email nor the username match any account at all. "
          "This is the most likely explanation: she may have registered under a "
          "different email, or never completed registration. Anti-enumeration means "
          "she'd see the same generic 'check your email' success message either way, "
          "so from her side it looks identical to a real failure.")

print()
print("=" * 60)
print("STEP 2: SMTP configuration (values hidden, presence only)")
print("=" * 60)
for key in ["EMAIL_HOST", "EMAIL_PORT", "EMAIL_HOST_USER", "EMAIL_USE_SSL", "DEFAULT_FROM_EMAIL"]:
    val = getattr(settings, key, None)
    print(f"  {key} = {val!r}")
print(f"  EMAIL_HOST_PASSWORD set: {bool(getattr(settings, 'EMAIL_HOST_PASSWORD', ''))}")

print()
print("=" * 60)
print("STEP 3: Live SMTP send test (sends a real test email to yourself)")
print("=" * 60)
TEST_RECIPIENT = "enquiries@pokebulk.co.za"  # change if you'd rather it land elsewhere
try:
    sent = send_mail(
        subject="PokeBulk SA - SMTP diagnostic test",
        message="This is a test email from diagnose_password_reset.py to confirm outbound SMTP is working.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[TEST_RECIPIENT],
        fail_silently=False,
    )
    print(f"  send_mail() returned {sent} (1 = sent successfully) to {TEST_RECIPIENT}")
    print("  Check that inbox (and spam) now -- if it arrives, SMTP itself is fine "
          "and the issue is specific to the reset flow or her account/email.")
except Exception as e:
    print(f"  FAILED: SMTP send FAILED: {type(e).__name__}: {e}")
    print("  This means outbound email is broken site-wide right now, not just for "
          "this one customer -- worth checking cPanel mail credentials/status.")
