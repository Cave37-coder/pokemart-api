"""
send_accessories_email.py -- 2026-11-11

One-off "new accessories" announcement to every customer (Michael: "drop an
update to all users with all the accessories"). Same safety model as
send_feature_update_email:

    # 1. Test -- ONE email, to Michael's own account only:
    python manage.py send_accessories_email

    # 2. Real send -- every active, non-unsubscribed customer (deduped by
    #    email address):
    python manage.py send_accessories_email --live

Run in the Railway shell (MAILERSEND_API_KEY only exists there). Prices are
the ones in accessories/data/temu_nov2026_listings.csv -- update PRODUCTS
below if you change a price before sending.
"""
import logging
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

from users.management.commands.send_feature_update_email import FOOTER_LEGAL, TEST_RECIPIENT_EMAIL

logger = logging.getLogger(__name__)

SUBJECT = "New at PokeBulk SA: sleeves, binders & top loaders"

# (heading, blurb, [(item, price)])
PRODUCTS = [
    ("🛡️ Sleeves (100 per pack)",
     "Protect every pull. Clear, matte or Yu-Gi-Oh! size, all sold in packs of 100.",
     [("Crystal clear sleeves, 64x89mm (snug fit for Pokémon)", "R40"),
      ("Crystal clear sleeves, 66x91mm (outer sleeve)", "R40"),
      ("Yu-Gi-Oh! perfect fit sleeves, 61x88mm", "R35"),
      ("Matte black sleeves", "R110")]),
    ("💎 Top loaders",
     "3x4\" top loaders, each with a soft sleeve included. Sold individually, or grab a bundle.",
     [("Top loader + sleeve (single)", "R8"),
      ("Top loader + sleeve, 10 pack", "R80")]),
    ("📒 Binders & albums",
     "From a first binder to a whole-collection album.",
     [("Starter binder, 160 pockets, red", "R120"),
      ("Top loader binder, 160 pockets, leather cover + zip (Black, Grey or Blue)", "R285"),
      ("Collector's binder, 480 pockets (Deep Blue or Grey)", "R510"),
      ("XL album, 1,280 card capacity, orange", "R1,010")]),
    ("📦 Deck boxes",
     "Flip-top PU-leather deck boxes with a card window. Every deck gets a home.",
     [("Flip-top deck box, black (single)", "R170")]),
]


def _section(heading, blurb, items, bg, border):
    rows = "".join(
        f'<tr><td style="font-size:13px;color:#444;padding:5px 0;border-bottom:1px solid {border}">{name}</td>'
        f'<td align="right" style="font-size:13px;font-weight:700;color:#1a1a2e;padding:5px 0 5px 12px;'
        f'border-bottom:1px solid {border};white-space:nowrap">{price}</td></tr>'
        for name, price in items
    )
    return f'''<tr><td style="padding:12px 32px 4px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{bg};border:1px solid {border};border-radius:10px">
    <tr><td style="padding:18px 22px">
      <div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:6px">{heading}</div>
      <p style="font-size:13px;color:#444;line-height:1.6;margin:0 0 8px">{blurb}</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>
    </td></tr>
  </table>
</td></tr>'''


def _build_email_html(display_name, site_url, unsubscribe_url):
    colours = [("#fff7f2", "#ffddc7"), ("#f5f7ff", "#d9e0ff"), ("#f2fbf5", "#cdeedd"), ("#fdf6ff", "#ecd5f7")]
    sections = "\n".join(
        _section(h, b, items, *colours[i % len(colours)]) for i, (h, b, items) in enumerate(PRODUCTS)
    )
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New accessories at PokeBulk SA</title></head>
<body style="margin:0;padding:0;background:#f2efe9;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2efe9;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden">
<tr><td style="background:#ff6b35;height:5px;line-height:5px;font-size:0">&nbsp;</td></tr>
<tr><td style="padding:28px 32px 4px">
  <div style="font-size:22px;font-weight:800;color:#1a1a2e">PokeBulk <span style="color:#ff6b35">SA</span></div>
  <div style="font-size:12px;color:#999;margin-top:2px">pokebulk.co.za</div>
</td></tr>
<tr><td style="padding:16px 32px 0">
  <p style="font-size:16px;color:#1a1a2e;margin:0 0 12px">Hey {display_name}! 👋</p>
  <p style="font-size:14px;color:#444;line-height:1.6;margin:0 0 4px">
    Our new <strong>Accessories</strong> range is live: sleeves, top loaders, binders and deck boxes, so your
    cards have somewhere safe to live. Everything below is on the site now and goes straight into
    <strong>My Pile</strong> with your cards.
  </p>
</td></tr>
{sections}
<tr><td style="padding:16px 32px 4px" align="center">
  <a href="{site_url}/accessories" style="display:inline-block;background:#ff6b35;color:#fff;text-decoration:none;font-size:14px;font-weight:700;padding:12px 28px;border-radius:8px">Shop Accessories &rarr;</a>
  <p style="font-size:12px;color:#999;margin:10px 0 0">Limited stock on some lines, so grab yours while they last.</p>
</td></tr>
<tr><td style="padding:20px 32px 28px;border-top:1px solid #eee">
  <p style="font-size:11px;color:#999;line-height:1.7;text-align:center;margin:16px 0 0">
    You're getting this because you have a PokeBulk SA account.<br>
    <a href="{unsubscribe_url}" style="color:#999">Unsubscribe from update emails</a> &mdash; order and account emails will still reach you either way.<br>
    {FOOTER_LEGAL}
  </p>
</td></tr>
</table>
</td></tr>
</table>
</body></html>'''


class Command(BaseCommand):
    help = "Sends the Nov 2026 'new accessories' announcement (test mode unless --live)."

    def add_arguments(self, parser):
        parser.add_argument("--live", action="store_true",
                            help="Send to every real customer instead of the one-email test address.")

    def handle(self, *args, **options):
        from users.views import make_unsubscribe_token
        User = get_user_model()
        site_url = getattr(settings, "SITE_URL", "https://pokebulk.co.za")
        api_url = getattr(settings, "API_URL", "https://pokemart-api-production.up.railway.app")

        if not options["live"]:
            self.stdout.write(self.style.WARNING(
                f"TEST MODE -- sending ONE email to {TEST_RECIPIENT_EMAIL}. Re-run with --live once it looks right."))
            try:
                user = User.objects.get(email__iexact=TEST_RECIPIENT_EMAIL)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"No account with email {TEST_RECIPIENT_EMAIL}."))
                return
            ok = self._send_one(user, site_url, api_url, make_unsubscribe_token)
            self.stdout.write(self.style.SUCCESS("Test email sent -- check inbox and spam.") if ok
                              else self.style.ERROR("Test send failed -- nothing went to customers."))
            return

        qs = (User.objects.filter(is_active=True, update_emails_opt_out=False)
              .exclude(email="").order_by("id"))
        self.stdout.write(f"LIVE SEND -- up to {qs.count()} accounts. Starting...")
        seen, sent, failed, dupes = set(), 0, 0, 0
        for user in qs.iterator():
            key = user.email.strip().lower()
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            if self._send_one(user, site_url, api_url, make_unsubscribe_token):
                sent += 1
            else:
                failed += 1
            if (sent + failed) % 25 == 0:
                self.stdout.write(f"... {sent} sent, {failed} failed so far")
            time.sleep(0.2)  # stay under MailerSend's API rate limit
        self.stdout.write(self.style.SUCCESS(f"Done. Sent: {sent}  Failed: {failed}  Skipped (duplicate email): {dupes}"))

    def _send_one(self, user, site_url, api_url, make_unsubscribe_token):
        name = (user.first_name or user.username or "Trainer").strip()
        unsub = f"{api_url}/api/auth/unsubscribe/{make_unsubscribe_token(user)}/"
        html = _build_email_html(name, site_url, unsub)
        msg = EmailMultiAlternatives(subject=SUBJECT, body=strip_tags(html), to=[user.email])
        msg.attach_alternative(html, "text/html")
        try:
            msg.send(fail_silently=False)
            return True
        except Exception:
            logger.exception("Failed to send accessories email to user %s (%s)", user.id, user.email)
            return False
