"""
send_feature_update_email.py

One-off "what's new on PokeBulk SA" email -- explains the Community system
in full, plus the September 2026 Checklists upgrades (Michael, 2026-09-02:
"can we do an email to all users... I just want this on to go out to hook
more people into the community!").

SAFE BY DEFAULT: with no flags, this sends exactly ONE email -- to
Michael's own account -- so the real design/copy can be eyeballed in an
actual inbox before anything goes to a real customer. Nothing else is
touched until --live is passed.

Usage (Railway shell -- MAILERSEND_API_KEY only exists there, not local
dev, same as every other MailerSend-dependent script in this folder):

    # 1. Test -- sends ONE email, to Michael's own account only:
    python manage.py send_feature_update_email

    # 2. Once that looks right in the inbox, the real send -- every
    #    active, non-unsubscribed customer with an email on file:
    python manage.py send_feature_update_email --live

Respects User.update_emails_opt_out and only emails is_active accounts
with a non-blank email. De-duplicates by email address (some accounts
share one -- see sync_duplicate_email_password.py) so nobody gets it
twice. A small delay between sends keeps this well under MailerSend's
API rate limit.
"""
import time
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth import get_user_model
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

TEST_RECIPIENT_EMAIL = "pokebulk77@gmail.com"
SUBJECT = "What's new on PokeBulk SA: meet the Community + faster Checklists"

FOOTER_LEGAL = (
    "Poke Bulk SA (Pty) Ltd &middot; Reg. No: 2024/615040/07 &middot; "
    "Unit 4, Sunkist Village, 11 Heliose Street, Birchleigh North, Kempton Park "
    "&middot; enquiries@pokebulk.co.za"
)


def _build_email_html(display_name, site_url, unsubscribe_url):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What's new on PokeBulk SA</title></head>
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
    We've shipped two things on the site worth knowing about: a proper <strong>Community</strong> for trainers to
    connect and trade, and a big upgrade to <strong>Checklists</strong>. Here's what's new.
  </p>
</td></tr>

<tr><td style="padding:20px 32px 4px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fff7f2;border:1px solid #ffddc7;border-radius:10px">
    <tr><td style="padding:20px 22px">
      <div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:8px">🤝 Meet the Community</div>
      <p style="font-size:13px;color:#444;line-height:1.6;margin:0 0 10px">
        A place to show off your collection, see what other trainers are chasing, and trade cards with people who
        already have what you need.
      </p>
      <ul style="font-size:13px;color:#444;line-height:1.7;margin:0 0 10px;padding-left:18px">
        <li><strong>Trainer Profile</strong> &mdash; turn it on from your Profile page ("Community Profile") to show
          your Pok&eacute;dex stats, your most recent catches and your wishlist to everyone browsing Community.
          It also switches on a <strong>free 5% discount on every order</strong>, automatically, for as long as it's on.</li>
        <li><strong>Browse Trainers</strong> &mdash; search and look through everyone else's public profile.</li>
        <li><strong>Most Wanted</strong> &mdash; a live, site-wide list of the cards the community wants most right now
          (only counted from public profiles, so it's real, actionable demand).</li>
        <li><strong>Friends</strong> &mdash; add someone as a friend and you both unlock a lot more than the public
          profile shows: your <em>full</em> Pok&eacute;dex (every card you've caught) and your <em>full</em> Checklist
          (exactly what you have and what you still need, set by set) &mdash; shared privately, just between the two of you.</li>
        <li><strong>Messages &amp; Trades</strong> &mdash; message friends directly, or send a trade request straight
          off someone's wishlist, if they've opted in to messages.</li>
        <li><strong>You're always in control</strong> &mdash; every part of this is opt-in, you can block anyone or
          report a message to us, and your collection's Rand value is never shown to anyone, ever.</li>
      </ul>
      <a href="{site_url}/community" style="display:inline-block;background:#ff6b35;color:#fff;text-decoration:none;font-size:13px;font-weight:700;padding:10px 20px;border-radius:6px;margin-top:4px">Visit Community &rarr;</a>
    </td></tr>
  </table>
</td></tr>

<tr><td style="padding:16px 32px 4px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7ff;border:1px solid #d9e0ff;border-radius:10px">
    <tr><td style="padding:20px 22px">
      <div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:8px">📋 Checklists just got a lot more useful</div>
      <ul style="font-size:13px;color:#444;line-height:1.7;margin:0 0 10px;padding-left:18px">
        <li><strong>Export to CSV</strong> &mdash; the Full List (every card + variant in a set, showing what you
          already own) or the Needed List (just what's missing, laid out as Card&nbsp;#/Name/Variant).</li>
        <li><strong>Printable Pull Sheets</strong> &mdash; a proper branded checklist page, landscape, laid out in
          columns so even a full set fits on about 2 pages, with missing cards highlighted in red so they're easy
          to spot at a glance.</li>
        <li><strong>Download PDF</strong> &mdash; one click and it's saved, no fiddling with your printer settings.</li>
        <li><strong>Email your Needed List to us</strong> &mdash; one button sends your want-list straight to our
          decklists inbox so we can start pulling stock for you.</li>
      </ul>
      <a href="{site_url}/checklists" style="display:inline-block;background:#5468ff;color:#fff;text-decoration:none;font-size:13px;font-weight:700;padding:10px 20px;border-radius:6px;margin-top:4px">Open Checklists &rarr;</a>
    </td></tr>
  </table>
</td></tr>

<tr><td style="padding:24px 32px 8px">
  <p style="font-size:13px;color:#444;line-height:1.6;margin:0">
    Thanks for being part of PokeBulk SA &mdash; more updates coming soon!
  </p>
</td></tr>

<tr><td style="padding:20px 32px 28px;border-top:1px solid #eee;margin-top:8px">
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
    help = "Sends the Sept 2026 'Community + Checklists' feature update email."

    def add_arguments(self, parser):
        parser.add_argument(
            '--live', action='store_true',
            help='Send to every real customer instead of the one-email test address.',
        )

    def handle(self, *args, **options):
        from users.views import make_unsubscribe_token
        User = get_user_model()
        site_url = getattr(settings, 'SITE_URL', 'https://pokebulk.co.za')
        api_url = getattr(settings, 'API_URL', 'https://pokemart-api-production.up.railway.app')
        live = options['live']

        if not live:
            self.stdout.write(self.style.WARNING(
                f"TEST MODE -- sending ONE email to {TEST_RECIPIENT_EMAIL}. "
                "Re-run with --live once it looks right in that inbox."
            ))
            try:
                user = User.objects.get(email__iexact=TEST_RECIPIENT_EMAIL)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"No account found with email {TEST_RECIPIENT_EMAIL} -- can't send a realistic test."
                ))
                return
            ok = self._send_one(user, site_url, api_url, make_unsubscribe_token)
            if ok:
                self.stdout.write(self.style.SUCCESS(
                    f"Test email sent to {TEST_RECIPIENT_EMAIL}. Check that inbox (and spam folder). "
                    "If it looks right, run again with --live to send to every customer."
                ))
            else:
                self.stdout.write(self.style.ERROR("Test send failed -- see the log above. Nothing was sent to customers."))
            return

        qs = (
            User.objects.filter(is_active=True, update_emails_opt_out=False)
            .exclude(email='')
            .order_by('id')
        )
        total = qs.count()
        self.stdout.write(f"LIVE SEND -- up to {total} accounts. Starting...")

        seen_emails = set()
        sent, failed, skipped_dupe = 0, 0, 0
        for user in qs.iterator():
            email_lower = user.email.strip().lower()
            if email_lower in seen_emails:
                skipped_dupe += 1
                continue
            seen_emails.add(email_lower)

            ok = self._send_one(user, site_url, api_url, make_unsubscribe_token)
            if ok:
                sent += 1
            else:
                failed += 1

            if (sent + failed) % 25 == 0:
                self.stdout.write(f"... {sent} sent, {failed} failed so far")
            time.sleep(0.2)  # stay well under MailerSend's API rate limit

        self.stdout.write(self.style.SUCCESS(
            f"Done. Sent: {sent}  Failed: {failed}  Skipped (duplicate email): {skipped_dupe}"
        ))
        if failed:
            self.stdout.write(self.style.WARNING(
                "Some sends failed -- check the Railway logs for 'Failed to send feature-update email' for details."
            ))

    def _send_one(self, user, site_url, api_url, make_unsubscribe_token):
        display_name = (user.first_name or user.username or 'Trainer').strip()
        token = make_unsubscribe_token(user)
        unsubscribe_url = f"{api_url}/api/auth/unsubscribe/{token}/"
        html = _build_email_html(display_name, site_url, unsubscribe_url)
        text_body = strip_tags(html)
        email = EmailMultiAlternatives(subject=SUBJECT, body=text_body, to=[user.email])
        email.attach_alternative(html, 'text/html')
        try:
            email.send(fail_silently=False)
            return True
        except Exception:
            logger.exception("Failed to send feature-update email to user %s (%s)", user.id, user.email)
            return False
