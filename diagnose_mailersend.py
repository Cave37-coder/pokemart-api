"""
diagnose_mailersend.py

The two older diagnostic scripts in this folder (diagnose_password_reset.py,
test_gmail_deliverability.py) test the OLD raw-SMTP setup and are stale --
email was switched to MailerSend's HTTPS API on 2026-07-27 (Railway blocks
outbound SMTP entirely). This is the up-to-date equivalent for the current
MailerSendBackend.

Run this on PRODUCTION (Railway shell), not local dev -- local dev's .env
doesn't have MAILERSEND_API_KEY set at all, so it will always fail locally
regardless of whether production is actually broken.

Usage (Railway):
    railway run python manage.py shell -c "exec(open('diagnose_mailersend.py').read())"

    -- or, from the Railway dashboard's own web shell / SSH into the service:
    python manage.py shell -c "exec(open('diagnose_mailersend.py').read())"

Makes NO account changes. Sends exactly one real test email if config looks OK.
"""

import requests
from django.conf import settings

print("=" * 70)
print("STEP 1: Config presence check")
print("=" * 70)
backend = getattr(settings, "EMAIL_BACKEND", None)
api_key = getattr(settings, "MAILERSEND_API_KEY", "")
from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
print(f"  EMAIL_BACKEND     = {backend!r}")
print(f"  MAILERSEND_API_KEY set = {bool(api_key)} (length={len(api_key)})")
print(f"  DEFAULT_FROM_EMAIL = {from_email!r}")

if backend != "config.mailersend_backend.MailerSendBackend":
    print("\n  !! EMAIL_BACKEND is NOT set to the MailerSend backend. That alone")
    print("     would explain total failure -- check Railway Variables / settings.py.")

if not api_key:
    print("\n  !! MAILERSEND_API_KEY is empty/unset in this environment.")
    print("     Check Railway -> service -> Variables. If it's set there but shows")
    print("     empty here, the deploy may be running against a stale env snapshot --")
    print("     a redeploy after confirming the variable usually fixes that.")
    print("\nStopping here -- can't test the API without a key.")
else:
    print()
    print("=" * 70)
    print("STEP 2: Direct MailerSend API call (bypasses Django, isolates the API itself)")
    print("=" * 70)
    TEST_RECIPIENT = "enquiries@pokebulk.co.za"  # change if you'd rather it land elsewhere
    resp = requests.post(
        "https://api.mailersend.com/v1/email",
        json={
            "from": {"email": "orders@pokebulk.co.za", "name": "PokeBulk SA"},
            "to": [{"email": TEST_RECIPIENT}],
            "subject": "PokeBulk SA - MailerSend diagnostic test",
            "text": "Direct API call from diagnose_mailersend.py to isolate the MailerSend API itself from Django's send_mail() plumbing.",
        },
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    )
    print(f"  HTTP status: {resp.status_code}")
    print(f"  Response body: {resp.text[:2000]}")
    if resp.status_code in (200, 201, 202):
        print(f"\n  MailerSend ACCEPTED the request. Check {TEST_RECIPIENT} (inbox + spam).")
        print("  If it never arrives, the problem is downstream of MailerSend")
        print("  (domain SPF/DKIM/DMARC, or MailerSend holding/queuing it) rather")
        print("  than the API call itself -- worth checking the MailerSend")
        print("  dashboard's Activity log for this message's delivery status.")
    else:
        print("\n  MailerSend REJECTED the request -- the body above has the exact reason.")
        print("  Common causes at this point:")
        print("    - 401/403: API key invalid, revoked, or expired")
        print("    - 422 #MS42207 'The from.email domain must be verified in your")
        print("      account to send emails' -- pokebulk.co.za's SPF/DKIM/DMARC DNS")
        print("      verification in MailerSend has lapsed or was never (re)completed.")
        print("      Check MailerSend dashboard -> Domains -> pokebulk.co.za status.")
        print("    - 422 trial-account restriction -- unverified-domain/trial accounts")
        print("      silently limit recipients to the account owner's own email until")
        print("      the sending domain is fully verified. This is the single most")
        print("      common reason MailerSend 'suddenly' stops working for real")
        print("      customers while test sends to your own inbox still work.")
        print("    - 429: rate limited / plan sending limit reached")

    print()
    print("=" * 70)
    print("STEP 3: Full Django pipeline test (send_mail -> MailerSendBackend)")
    print("=" * 70)
    from django.core.mail import send_mail
    try:
        sent = send_mail(
            subject="PokeBulk SA - Django pipeline diagnostic test",
            message="Testing the full send_mail() -> MailerSendBackend -> MailerSend API path.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[TEST_RECIPIENT],
            fail_silently=False,
        )
        print(f"  send_mail() returned {sent} (1 = MailerSend accepted it).")
    except Exception as e:
        print(f"  send_mail() FAILED: {type(e).__name__}: {e}")
        print("  If STEP 2's raw API call succeeded but this fails, the bug is in")
        print("  MailerSendBackend's payload building, not the API/account itself.")
