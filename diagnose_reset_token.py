"""
diagnose_reset_token.py

Read-only diagnostic for "the reset link says invalid/expired even though
it was JUST sent" -- a different symptom from diagnose_mailersend.py /
diagnose_password_reset.py (both of those check EMAIL DELIVERY; this one
checks TOKEN VALIDATION, since Michael confirmed 2026-08-07 the email
itself arrives fine, it's specifically the link that immediately fails).

What "invalid or expired" from PasswordResetConfirmView actually means:
  1. uid doesn't base64-decode to a real, active user's pk, OR
  2. default_token_generator.check_token(user, token) returns False

(2) is by far the more likely one if delivery is fine. Django's token
hash is built from: the user's pk, a timestamp, the user's CURRENT
password hash, and the user's CURRENT last_login timestamp. So a
freshly-minted token becomes "invalid" the instant ANY of those three
change -- most commonly: the customer logs in again (on this device or
another) while waiting for the email to arrive, which bumps last_login
and invalidates every reset token that was already sent out, even ones
issued seconds earlier. That's the #1 real-world cause of this exact
complaint and doesn't require any code fix -- just customer education
("don't try logging in again after requesting a reset, wait for the
email"). This script rules the other, fixable causes in or out first.

Usage (Railway Console, same pattern as the other diagnose_*.py scripts):
    python manage.py shell -c "exec(open('diagnose_reset_token.py').read())"

Makes NO changes to any account -- the round-trip test in STEP 3 mints
and checks a token in memory only, nothing is saved.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
import hashlib

User = get_user_model()

print("=" * 60)
print("STEP 1: Settings that affect token validity")
print("=" * 60)
timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200)
print(f"  PASSWORD_RESET_TIMEOUT = {timeout} seconds (~{timeout / 3600:.1f} hours)"
      f"{'  <-- default, nothing overriding it' if not hasattr(settings, 'PASSWORD_RESET_TIMEOUT') else ''}")
print(f"  SITE_URL = {getattr(settings, 'SITE_URL', '(not set, falls back to https://pokebulk.co.za)')!r}")
# Not printing SECRET_KEY itself -- a short fingerprint is enough to tell
# whether it's the same value across two separate runs of this script
# (e.g. run it now, redeploy, run it again -- if the fingerprint changes,
# SECRET_KEY is NOT stable across deploys, which would invalidate every
# outstanding reset link on every redeploy).
fp = hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:12]
print(f"  SECRET_KEY fingerprint = {fp}  (re-run this after a redeploy -- if this "
      f"value changes, that's the bug: every token becomes invalid on every deploy)")

print()
print("=" * 60)
print("STEP 2: Pick a real user to test against (first active superuser)")
print("=" * 60)
user = User.objects.filter(is_active=True, is_superuser=True).order_by("id").first()
if not user:
    user = User.objects.filter(is_active=True).order_by("id").first()
if not user:
    print("  No active users found at all -- can't run the round-trip test.")
else:
    print(f"  Using: username={user.username!r} id={user.pk} last_login={user.last_login}")

    print()
    print("=" * 60)
    print("STEP 3: Mint + immediately check a token (in-memory only, nothing saved)")
    print("=" * 60)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    print(f"  Minted uid={uid} token={token}")

    # Re-fetch fresh from DB, exactly like PasswordResetConfirmView does,
    # instead of reusing the in-memory `user` object -- if there's any kind
    # of caching/staleness issue this is where it'd show up.
    decoded_id = force_str(urlsafe_base64_decode(uid))
    fresh_user = User.objects.get(pk=decoded_id, is_active=True)
    ok = default_token_generator.check_token(fresh_user, token)
    print(f"  check_token() result: {'VALID' if ok else 'INVALID <-- BUG if you see this'}")

    if ok:
        print("  Round-trip works fine within this one process/request. If real")
        print("  customer links are STILL failing immediately, the most likely")
        print("  explanations left are:")
        print("    a) the customer logged in again (this device or another) while")
        print("       waiting for the email -- that updates last_login and silently")
        print("       invalidates every already-sent reset link for their account")
        print("    b) they clicked an OLD reset email from a previous attempt, not")
        print("       the most recent one -- ask them to search their inbox for the")
        print("       newest 'Reset your PokeBulk SA password' email specifically")
        print("    c) SECRET_KEY fingerprint above changed since the link was sent")
        print("       (only diagnosable by comparing fingerprints before/after a")
        print("       redeploy that happened in between)")
    else:
        print("  This is a genuine bug -- token minted and checked in the SAME")
        print("  process, seconds apart, for an untouched user, still failed.")
        print("  Worth checking Django/simplejwt version pins didn't drift, and")
        print("  whether USE_TZ / a custom AUTH_USER_MODEL field is involved.")
