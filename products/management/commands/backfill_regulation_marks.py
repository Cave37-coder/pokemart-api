"""
Backfills CardSet.regulation_mark from the pokemontcg.io API.

For each CardSet with a tcgio_code set, fetches one card from that set via
pokemontcg.io and reads its regulationMark field. Regulation mark is a
property of the printing/set, not the individual card, so any card in the
set will report the same value.

Usage:
    python manage.py backfill_regulation_marks            # do it for real
    python manage.py backfill_regulation_marks --dry-run   # preview only
"""
import time
import requests
from django.core.management.base import BaseCommand
from products.models import CardSet

POKEMONTCGIO_BASE = "https://api.pokemontcg.io/v2"
REQUEST_DELAY_SECONDS = 0.3  # be polite to the free-tier rate limit


class Command(BaseCommand):
    help = "Backfill CardSet.regulation_mark from pokemontcg.io"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving anything.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite regulation_mark even on sets that already have a value set.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        qs = CardSet.objects.exclude(tcgio_code="").order_by("code")
        if not force:
            qs = qs.filter(regulation_mark="")

        no_tcgio_code = CardSet.objects.filter(tcgio_code="").order_by("code")

        total = qs.count()
        self.stdout.write(f"Checking {total} set(s) with a tcgio_code set...")

        updated = 0
        no_mark_found = []
        errors = []

        for card_set in qs:
            try:
                resp = requests.get(
                    f"{POKEMONTCGIO_BASE}/cards",
                    params={"q": f"set.id:{card_set.tcgio_code}", "pageSize": 1},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])

                if not data:
                    no_mark_found.append((card_set.code, "no cards returned for this tcgio_code"))
                    continue

                mark = data[0].get("regulationMark", "")

                if not mark:
                    no_mark_found.append((card_set.code, "card found but no regulationMark field (likely pre-regulation-mark era set)"))
                    continue

                self.stdout.write(f"  [{card_set.code}] {card_set.name}: regulation_mark -> '{mark}'")

                if not dry_run:
                    card_set.regulation_mark = mark
                    card_set.save(update_fields=["regulation_mark"])

                updated += 1

            except requests.RequestException as e:
                errors.append((card_set.code, str(e)))

            time.sleep(REQUEST_DELAY_SECONDS)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{'Would update' if dry_run else 'Updated'} {updated} set(s)."
        ))

        if no_mark_found:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"{len(no_mark_found)} set(s) had no regulation mark available (likely pre-Sword & Shield era — expected, not an error):"
            ))
            for code, reason in no_mark_found:
                self.stdout.write(f"  [{code}] {reason}")

        if errors:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"{len(errors)} set(s) failed due to request errors:"))
            for code, err in errors:
                self.stdout.write(f"  [{code}] {err}")

        empty_tcgio = list(no_tcgio_code.values_list("code", "name"))
        if empty_tcgio:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"{len(empty_tcgio)} set(s) have no tcgio_code set, so they were skipped entirely "
                f"and need a manual lookup (e.g. from Bulbapedia's set infobox):"
            ))
            for code, name in empty_tcgio:
                self.stdout.write(f"  [{code}] {name}")
