"""
diagnose_reset_confirm_live.py

End-to-end, REAL-HTTPS reproduction of "reset password succeeds, redirected
to login, but the new password is rejected -- with no repeated attempts."
Uses a disposable throwaway account created and destroyed by this script,
so it can never touch a real customer's account or password.

Hits the live production API exactly like the frontend does (same two
endpoints, same JSON shape, real HTTP round trip) rather than calling the
view code in-process, so it will also catch anything environment-specific
(load balancing, stale worker, etc) that an in-process shell test wouldn't.

Usage:
    python manage.py shell -c "exec(open('diagnose_reset_confirm_live.py').read())"

Safe to re-run -- always cleans up its own test user first and last.
"""

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

User = get_user_model()
BASE = "https://pokemart-api-production.up.railway.app"

TEST_USERNAME = "diag_reset_test_tmp"
TEST_EMAIL = "diag_reset_test_tmp@example.com"
OLD_PASSWORD = "DiagOldPass123!"
NEW_PASSWORD = "DiagNewPass456!"

User.objects.filter(username=TEST_USERNAME).delete()

print("=" * 60)
print("STEP 1: Create a throwaway test user (deleted at the end)")
print("=" * 60)
user = User.objects.create_user(
    username=TEST_USERNAME, email=TEST_EMAIL, password=OLD_PASSWORD, is_active=True
)
print(f"  created id={user.pk} username={TEST_USERNAME!r}")

uid = urlsafe_base64_encode(force_bytes(user.pk))
token = default_token_generator.make_token(user)
print(f"  uid={uid} token={token}")

print()
print("=" * 60)
print("STEP 2: POST /api/auth/password-reset/confirm/ over real HTTPS")
print("        (exactly what the reset-password page sends)")
print("=" * 60)
r = requests.post(
    f"{BASE}/api/auth/password-reset/confirm/",
    json={"uid": uid, "token": token, "new_password": NEW_PASSWORD},
    timeout=20,
)
print(f"  status={r.status_code}")
print(f"  body={r.text}")

print()
print("=" * 60)
print("STEP 3: What does the database say right now?")
print("=" * 60)
user.refresh_from_db()
new_ok = user.check_password(NEW_PASSWORD)
old_ok = user.check_password(OLD_PASSWORD)
print(f"  check_password(NEW_PASSWORD) = {new_ok}")
print(f"  check_password(OLD_PASSWORD) = {old_ok}")
if new_ok:
    print("  -> The new password WAS saved correctly in the database.")
else:
    print("  -> BUG CONFIRMED: the new password was NOT saved, even though")
    print("     STEP 2 returned success. This points at set_password()/save()")
    print("     itself, or the DB write not actually committing.")

print()
print("=" * 60)
print("STEP 4: POST /api/auth/login/ with the NEW password over real HTTPS")
print("        (exactly what the login page sends)")
print("=" * 60)
r2 = requests.post(
    f"{BASE}/api/auth/login/",
    json={"username": TEST_USERNAME, "password": NEW_PASSWORD},
    timeout=20,
)
print(f"  status={r2.status_code}")
print(f"  body={r2.text[:400]}")
if r2.status_code == 200:
    print("  -> Login with the new password WORKED.")
else:
    print("  -> Login with the new password FAILED -- this is the bug, reproduced live.")

print()
print("=" * 60)
print("STEP 5: Cleanup")
print("=" * 60)
user.delete()
print("  throwaway test user deleted -- no trace left behind")
