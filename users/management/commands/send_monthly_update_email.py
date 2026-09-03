"""
send_monthly_update_email.py

Recurring "what's new this month" email -- new sets added to PokeBulk SA
since the 1st of the current month, auto-detected from CardSet.created_at
(added 2026-09-02 for exactly this). Michael, 2026-09-02: "add a script to
send out a mail on 20th of each month, just update on all added sets and
site updates, I just want this on to go out to hook more people into the
community!"

Also pulls in any products.SiteAnnouncement rows (restocks / general
announcements) whose `date` falls in the current month (added 2026-09-03).
Michael logs those himself from Django admin -- Products > Site
announcements -- no code change needed to add one.

Deliberately auto-generated from real data only (no freeform monthly copy
to remember to write) -- if nothing new was added this month, it SKIPS the
send entirely rather than emailing an empty "nothing to report". That
makes it safe to wire into a Railway Cron service with no human review
step each month, same pattern as the existing sync_prices cron
(railway.cron.toml) -- see the bottom of this docstring for how to do that.

SAFE BY DEFAULT here too: with no flags this only PRINTS what it would
send (no email at all) so you can check the list of new sets is right.
--live sends for real.

Usage (Railway shell):
    # 1. Dry run -- just prints which sets it found, sends nothing:
    python manage.py send_monthly_update_email

    # 2. Real send -- every active, non-unsubscribed customer:
    python manage.py send_monthly_update_email --live

To run this automatically on the 20th of every month:
    1. Railway dashboard -> New Service -> Empty Service (or duplicate the
       existing cron service that runs sync_prices_only).
    2. Same repo/branch as the main API service, but set its Start Command
       (Settings -> Deploy) to:
           python manage.py send_monthly_update_email --live
    3. Settings -> Cron Schedule -> "0 8 20 * *" (08:00 UTC = 10:00
       Johannesburg, on the 20th of every month).
    4. Give it the same environment variables as the main service
       (DATABASE_URL, MAILERSEND_API_KEY, etc.) -- Railway can "share"
       variables from another service in that same settings page.
Nothing about this touches the main site -- it's a separate one-shot
service that runs, sends (or skips) and stops, same as the prices cron.
"""
import time
import calendar
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

SUBJECT_TEMPLATE = "New on PokeBulk SA this month: {month_name}"


def _new_sets_this_month():
    """CardSet rows created since the 1st of the current month. Existing
    sets all backfilled to NULL created_at (see the migration), so they
    never show up here -- only sets added AFTER this feature shipped."""
    from products.models import CardSet
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return list(
        CardSet.objects.filter(created_at__gte=month_start)
        .select_related('era')
        .order_by('created_at')
    )


def _announcements_this_month():
    """SiteAnnouncement rows (restocks/announcements) whose `date` -- the
    field Michael sets in admin, not created_at -- falls in the current
    calendar month."""
    from products.models import SiteAnnouncement
    now = timezone.now()
    return list(
        SiteAnnouncement.objects.filter(date__year=now.year, date__month=now.month)
        .select_related('product')
        .order_by('date')
    )


def _build_sets_section(month_name, new_sets, site_url):
    if not new_sets:
        return ''
    rows_html = ''
    for s in new_sets:
        era_name = s.era.name if s.era else ''
        rows_html += f'''<tr><td style="padding:10px 0;border-bottom:1px solid #eee">
          <div style="font-size:14px;color:#1a1a2e;font-weight:700">{s.name} <span style="color:#999;font-weight:400">[{s.code}]</span></div>
          <div style="font-size:12px;color:#888">{era_name}{' &middot; ' if era_name else ''}{s.total_cards} cards</div>
        </td></tr>'''
    return f'''<tr><td style="padding:20px 32px 4px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fff7f2;border:1px solid #ffddc7;border-radius:10px">
    <tr><td style="padding:18px 22px">
      <div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:6px">🆕 New sets added in {month_name}</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
      <a href="{site_url}/checklists" style="display:inline-block;background:#5468ff;color:#fff;text-decoration:none;font-size:13px;font-weight:700;padding:10px 20px;border-radius:6px;margin-top:14px">Check off your collection &rarr;</a>
    </td></tr>
  </table>
</td></tr>'''


def _build_announcements_section(month_name, announcements, site_url):
    if not announcements:
        return ''
    rows_html = ''
    for a in announcements:
        label = 'Restock' if a.kind == 'restock' else 'Announcement'
        link = ''
        if a.product_id:
            link = f"{site_url}/products/{a.product_id}"
        elif a.link_url:
            link = a.link_url
        link_html = f'<a href="{link}" style="color:#2f9e5c;font-size:12px;font-weight:700;text-decoration:none">View &rarr;</a>' if link else ''
        body_html = f'<div style="font-size:12px;color:#888;margin-top:2px">{a.body}</div>' if a.body else ''
        extra_html = f'<div style="margin-top:6px">{link_html}</div>' if link_html else ''
        rows_html += f'''<tr><td style="padding:10px 0;border-bottom:1px solid #e3f5ea">
          <div style="font-size:14px;color:#1a1a2e;font-weight:700">[{label}] {a.title}</div>
          {body_html}
          {extra_html}
        </td></tr>'''
    return f'''<tr><td style="padding:20px 32px 4px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2fbf5;border:1px solid #cdeedd;border-radius:10px">
    <tr><td style="padding:18px 22px">
      <div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:6px">📣 Restocks &amp; announcements in {month_name}</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
    </td></tr>
  </table>
</td></tr>'''


def _build_email_html(display_name, site_url, unsubscribe_url, month_name, new_sets, announcements):
    sets_section = _build_sets_section(month_name, new_sets, site_url)
    announcements_section = _build_announcements_section(month_name, announcements, site_url)

    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New on PokeBulk SA this month</title></head>
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
    Here's what's new on the site this month.
  </p>
</td></tr>

{sets_section}{announcements_section}

<tr><td style="padding:20px 32px 8px">
  <p style="font-size:13px;color:#444;line-height:1.6;margin:0">
    Don't forget &mdash; the <a href="{site_url}/community" style="color:#ff6b35">Community</a> is the easiest way to trade for what you're missing.
    A public Trainer Profile also gets you 5% off every order, automatically.
  </p>
</td></tr>

<tr><td style="padding:20px 32px 28px;border-top:1px solid #eee;margin-top:8px">
  <p style="font-size:11px;color:#999;line-height:1.7;text-align:center;margin:16px 0 0">
    You're getting this because you have a PokeBulk SA account.<br>
    <a href="{unsubscribe_url}" style="color:#999">Unsubscribe from update emails</a> &mdash; order and account emails will still reach you either way.<br>
    Poke Bulk SA (Pty) Ltd &middot; Reg. No: 2024/615040/07 &middot;
    Unit 4, Sunkist Village, 11 Heliose Street, Birchleigh North, Kempton Park &middot; enquiries@pokebulk.co.za
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>'''


class Command(BaseCommand):
    help = "Sends the monthly 'new sets this month' digest email. Skips sending if nothing new was added."

    def add_arguments(self, parser):
        parser.add_argument(
            '--live', action='store_true',
            help='Actually send to every real customer. Without this, only prints what it would send.',
        )

    def handle(self, *args, **options):
        from users.views import make_unsubscribe_token
        User = get_user_model()
        live = options['live']
        site_url = getattr(settings, 'SITE_URL', 'https://pokebulk.co.za')
        api_url = getattr(settings, 'API_URL', 'https://pokemart-api-production.up.railway.app')

        new_sets = _new_sets_this_month()
        announcements = _announcements_this_month()
        month_name = calendar.month_name[timezone.now().month]

        if not new_sets and not announcements:
            self.stdout.write(self.style.WARNING(
                f"Nothing found for {month_name} (no new CardSets, no SiteAnnouncements) -- skipping, nothing sent."
            ))
            return

        self.stdout.write(f"Found {len(new_sets)} new set(s) for {month_name}:")
        for s in new_sets:
            self.stdout.write(f"  - {s.name} [{s.code}]")
        self.stdout.write(f"Found {len(announcements)} announcement(s)/restock(s) for {month_name}:")
        for a in announcements:
            self.stdout.write(f"  - [{a.kind}] {a.title} ({a.date})")

        if not live:
            self.stdout.write(self.style.WARNING(
                "DRY RUN -- nothing was sent. Re-run with --live to actually email every customer."
            ))
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

            display_name = (user.first_name or user.username or 'Trainer').strip()
            token = make_unsubscribe_token(user)
            unsubscribe_url = f"{api_url}/api/auth/unsubscribe/{token}/"
            html = _build_email_html(display_name, site_url, unsubscribe_url, month_name, new_sets, announcements)
            text_body = strip_tags(html)
            email = EmailMultiAlternatives(
                subject=SUBJECT_TEMPLATE.format(month_name=month_name),
                body=text_body, to=[user.email],
            )
            email.attach_alternative(html, 'text/html')
            try:
                email.send(fail_silently=False)
                sent += 1
            except Exception:
                logger.exception("Failed to send monthly update email to user %s (%s)", user.id, user.email)
                failed += 1

            if (sent + failed) % 25 == 0:
                self.stdout.write(f"... {sent} sent, {failed} failed so far")
            time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS(
            f"Done. Sent: {sent}  Failed: {failed}  Skipped (duplicate email): {skipped_dupe}"
        ))
