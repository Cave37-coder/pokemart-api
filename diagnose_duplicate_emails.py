"""
diagnose_duplicate_emails.py

Read-only audit: finds every email address shared by more than one
account. Directly tests the theory behind "reset password succeeds but
login still fails" -- PasswordResetRequestView picks the FIRST account
matching that email (User.objects.filter(email__iexact=email).first()),
which is not guaranteed to be the specific account you meant to log into
if more than one account was ever registered under the same address.

This would also be a mechanical explanation for customers ending up with
multiple profiles: unable to get back into their real account via reset,
they register a new one instead.

Makes NO changes. Safe to run anytime.

Usage:
    python manage.py shell -c "exec(open('diagnose_duplicate_emails.py').read())"
"""

from django.contrib.auth import get_user_model
from django.db.models import Count

User = get_user_model()

print("=" * 60)
print("Accounts sharing an email address (case-insensitive)")
print("=" * 60)

# Group in Python by lowercased email rather than a DB-level iexact
# GROUP BY, since Postgres COLLATE behaviour for that varies -- this is a
# one-time read of the whole user table, fine at this table size.
all_users = User.objects.all().order_by("id").values(
    "id", "username", "email", "is_active", "date_joined", "last_login"
)
by_email = {}
for u in all_users:
    key = (u["email"] or "").strip().lower()
    if not key:
        continue
    by_email.setdefault(key, []).append(u)

dupes = {email: users for email, users in by_email.items() if len(users) > 1}

if not dupes:
    print("  None found -- every email in the system maps to exactly one account.")
    print("  The duplicate-email theory is ruled out; the reset/login bug (if any)")
    print("  is something else specific to that session.")
else:
    print(f"  Found {len(dupes)} email address(es) shared by more than one account:\n")
    for email, users in sorted(dupes.items(), key=lambda kv: -len(kv[1])):
        print(f"  {email}  ({len(users)} accounts)")
        for u in sorted(users, key=lambda x: x["id"]):
            which_one_gets_reset = " <-- PasswordResetRequestView would reset THIS one" if u is users[0] else ""
            print(
                f"    id={u['id']:<6} username={u['username']!r:<22} active={u['is_active']!s:<5} "
                f"joined={u['date_joined']} last_login={u['last_login']}{which_one_gets_reset}"
            )
        print()
    print(f"  Total accounts affected: {sum(len(v) for v in dupes.values())}")
    print()
    print("  If your account is in this list: 'reset password' resets whichever")
    print("  row the DB happens to return first for that email (usually, but not")
    print("  guaranteed to be, the lowest id / oldest account) -- not necessarily")
    print("  the username you actually log in with day to day. That fully explains")
    print("  'reset says success, login still fails, no repeated attempts.'")
