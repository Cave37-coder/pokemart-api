"""
sync_duplicate_email_password.py

One-off, interactive-free helper: given a username whose password is
already correct (e.g. you just reset it and confirmed it works), copies
that SAME password hash onto every other active account sharing its email
address. Doesn't touch anything else on the sibling accounts.

Edit KNOWN_GOOD_USERNAME below before running -- defaults to Michael's own
'Ty' account (the one diag_reset_confirm_live/duplicate audit found was
actually reset), to sync onto 'CaVe37'.

Usage:
    python manage.py shell -c "exec(open('sync_duplicate_email_password.py').read())"
"""

from django.contrib.auth import get_user_model

User = get_user_model()

KNOWN_GOOD_USERNAME = "Ty"  # <-- change this if syncing a different account

source = User.objects.filter(username=KNOWN_GOOD_USERNAME).first()
if not source:
    print(f"No user found with username={KNOWN_GOOD_USERNAME!r} -- nothing to do.")
else:
    siblings = User.objects.filter(email__iexact=source.email, is_active=True).exclude(pk=source.pk)
    if not siblings.exists():
        print(f"{KNOWN_GOOD_USERNAME!r} has no other accounts sharing its email -- nothing to sync.")
    else:
        for sib in siblings:
            sib.password = source.password  # copy the hash directly, no need to know the raw password
            sib.save(update_fields=["password"])
            print(f"Synced password hash from {source.username!r} (id={source.pk}) -> {sib.username!r} (id={sib.pk})")
        print("Done. All of these usernames now log in with the same password.")
