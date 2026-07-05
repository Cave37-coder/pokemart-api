"""
test_gmail_deliverability.py

The earlier diagnostic sent its test email to enquiries@pokebulk.co.za --
same mail server, so it only proved local delivery works, not real
internet-facing deliverability. This sends to an actual external Gmail
address to check whether Gmail specifically is accepting or silently
dropping mail from mail.pokebulk.co.za.

Usage:
    python manage.py shell -c "exec(open('test_gmail_deliverability.py').read())"
"""

from django.core.mail import send_mail
from django.conf import settings

# Put a real Gmail address you can check here -- your own personal Gmail
# is fine, doesn't need to be hers.
TEST_RECIPIENT = "REPLACE_WITH_YOUR_OWN_GMAIL@gmail.com"

if TEST_RECIPIENT == "REPLACE_WITH_YOUR_OWN_GMAIL@gmail.com":
    print("Edit TEST_RECIPIENT in this file to a real Gmail address you can check, then re-run.")
else:
    try:
        sent = send_mail(
            subject="PokeBulk SA - Gmail deliverability test",
            message="Testing whether Gmail accepts mail from mail.pokebulk.co.za without dropping/spam-filtering it.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[TEST_RECIPIENT],
            fail_silently=False,
        )
        print(f"send_mail() returned {sent} -- SMTP accepted it for delivery.")
        print(f"Now check {TEST_RECIPIENT} (inbox AND spam) in the next few minutes.")
        print("If it never arrives at all (not even in spam), Gmail is likely silently")
        print("rejecting mail.pokebulk.co.za due to missing/misaligned SPF, DKIM, or DMARC records --")
        print("worth checking those DNS records for pokebulk.co.za next.")
    except Exception as e:
        print(f"SMTP send FAILED outright: {type(e).__name__}: {e}")
