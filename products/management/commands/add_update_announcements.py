"""
add_update_announcements.py

Adds this round of "what's new on the site" items as products.SiteAnnouncement rows,
so the existing update email (send_monthly_update_email) picks them up -- same thing
as typing them into staff > Restocks & Announcements, just in one go.
Michael, 2026-10-27: "update email for site", sent via the Restocks & Announcements tool.

Idempotent: an item with the same title is never created twice. Safe to re-run.

    /opt/venv/bin/python manage.py add_update_announcements --skip-checks            # adds them
    /opt/venv/bin/python manage.py add_update_announcements --skip-checks --dry-run  # just lists
Then preview the email (sends nothing):
    /opt/venv/bin/python manage.py send_monthly_update_email --skip-checks
and only when happy:
    /opt/venv/bin/python manage.py send_monthly_update_email --skip-checks --live
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

SITE = "https://pokebulk.co.za"

ITEMS = [
    {
        "title": "New: Card Condition Guide",
        "body": "What Near Mint, Lightly Played and the rest actually mean, side by side with PSA and Beckett grading, "
                "with every source linked. No more guessing what NM means.",
        "link_url": f"{SITE}/condition",
    },
    {
        "title": "New: How to spot fake & plastic Pokémon cards",
        "body": "A visual guide with diagrams: the light test, card back, fonts, energy symbols, holo and more. "
                "Stay safe when buying and trading.",
        "link_url": f"{SITE}/fake-cards",
    },
    {
        "title": "Smarter card search",
        "body": "Search now understands HP (try \"HP 30\"), attack names and ability names, not just card names.",
        "link_url": f"{SITE}/cards",
    },
    {
        "title": "Banking details on every EFT & collection order",
        "body": "Your order page and status-update emails now show our banking details, with your order number as the reference.",
        "link_url": "",
    },
    {
        "title": "\"My Sets\" and \"My Pokemon\"",
        "body": "Your checklists are now called My Sets, and your Pokémon collection is My Pokemon.",
        "link_url": f"{SITE}/checklists",
    },
]


class Command(BaseCommand):
    help = "Adds the current 'what's new on the site' items as SiteAnnouncement rows for the update email."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only list what would be added.")

    def handle(self, *args, **options):
        from products.models import SiteAnnouncement
        today = timezone.localdate()
        added = skipped = 0
        for item in ITEMS:
            exists = SiteAnnouncement.objects.filter(title=item["title"]).exists()
            if exists:
                skipped += 1
                self.stdout.write(f"  already there: {item['title']}")
                continue
            if options["dry_run"]:
                self.stdout.write(f"  would add: {item['title']}")
                continue
            SiteAnnouncement.objects.create(
                kind="announcement", title=item["title"], body=item["body"],
                date=today, link_url=item["link_url"],
            )
            added += 1
            self.stdout.write(self.style.SUCCESS(f"  added: {item['title']}"))
        self.stdout.write(f"Done. Added {added}, already present {skipped}. Entry date: {today}.")
