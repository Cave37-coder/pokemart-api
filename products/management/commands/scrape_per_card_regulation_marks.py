"""
Scrapes the per-card regulationMark from pokemontcg.io for every card in
every SV-era and MEG-era CardSet, and writes it to PokemonProduct.
regulation_mark.

Scoped to SV/MEG eras only: confirmed 2026-06-20 that regulation mark is NOT
always uniform within a set (e.g. Temporal Forces / sv5 is genuinely all
mark H, contradicting the previously-stored CardSet.regulation_mark of
'G' -- the original set-level sync data cannot be trusted for these eras).
Older eras' cards are already rotated out regardless of their exact mark,
so per-card precision there doesn't change any legality outcome and isn't
worth the scrape volume.

Matches cards by card_number: pulls the leading digits from pokemontcg.io's
"number" field (e.g. "025", "081a", "TG01") and compares against
PokemonProduct.card_number. Cards whose number doesn't parse to a plain
integer (alt-numbering subsets, promos, etc.) are reported as unmatched
for manual review rather than guessed at.

Usage:
    python manage.py scrape_per_card_regulation_marks --dry-run
    python manage.py scrape_per_card_regulation_marks
"""
import re
import os
import time
import requests
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import CardSet, PokemonProduct

POKEMONTCGIO_BASE = "https://api.pokemontcg.io/v2"

# Optional: set POKEMONTCGIO_API_KEY in your environment (or .env.local) to
# raise the rate limit from 1000/day + 30/min to 20,000/day. Get a free key
# at https://dev.pokemontcg.io -- takes about 2 minutes. Falls back to
# unauthenticated requests if unset.
API_KEY = os.environ.get("POKEMONTCGIO_API_KEY", "")
REQUEST_HEADERS = {"X-Api-Key": API_KEY} if API_KEY else {}

REQUEST_DELAY_SECONDS = 2.2 if not API_KEY else 0.3  # 30/min unauthenticated = ~1 every 2s, leave margin
MAX_RETRIES = 4
PAGE_SIZE = 250  # pokemontcg.io's max page size

TARGET_ERA_CODES = ["SV", "MEG"]

_LEADING_DIGITS_RE = re.compile(r'^(\d+)')


def parse_card_number(api_number):
    """Extract the leading integer from pokemontcg.io's number field,
    e.g. '025' -> 25, '081a' -> 81, 'TG01' -> None (no leading digits)."""
    match = _LEADING_DIGITS_RE.match(api_number.strip())
    if not match:
        return None
    return int(match.group(1))


def fetch_all_cards_for_set(tcgio_code):
    """Paginate through every card in a set -- never sample just one.
    Retries with exponential backoff on any request failure (including
    pokemontcg.io's rate-limit responses, which can surface as 429 or,
    confirmed 2026-06-20, sometimes as a misleading 404 when unauthenticated
    requests get throttled)."""
    all_cards = []
    page = 1
    while True:
        attempt = 0
        while True:
            try:
                resp = requests.get(
                    f"{POKEMONTCGIO_BASE}/cards",
                    params={"q": f"set.id:{tcgio_code}", "pageSize": PAGE_SIZE, "page": page},
                    headers=REQUEST_HEADERS,
                    timeout=20,
                )
                if resp.status_code in (429, 404) and attempt < MAX_RETRIES:
                    wait = (2 ** attempt) * 5
                    time.sleep(wait)
                    attempt += 1
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as e:
                if attempt < MAX_RETRIES:
                    wait = (2 ** attempt) * 5
                    time.sleep(wait)
                    attempt += 1
                    continue
                raise RuntimeError(f"request failed on page {page} after {MAX_RETRIES} retries: {e}")

        results = data.get("data", [])
        all_cards.extend(results)

        total_count = data.get("totalCount", len(all_cards))
        if len(all_cards) >= total_count or not results:
            break
        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_cards


class Command(BaseCommand):
    help = "Scrape per-card regulation marks from pokemontcg.io for SV/MEG era sets."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        target_sets = list(
            CardSet.objects.filter(era__code__in=TARGET_ERA_CODES)
            .exclude(tcgio_code="")
            .select_related("era")
            .order_by("code")
        )
        self.stdout.write(f"Scraping {len(target_sets)} set(s) across eras {TARGET_ERA_CODES}...\n")

        total_updated = 0
        total_unmatched = 0
        mixed_mark_sets = []

        for set_index, card_set in enumerate(target_sets):
            if set_index > 0:
                time.sleep(REQUEST_DELAY_SECONDS)
            try:
                api_cards = fetch_all_cards_for_set(card_set.tcgio_code)
            except RuntimeError as e:
                self.stdout.write(self.style.ERROR(f"  [{card_set.code}] FAILED: {e}"))
                continue

            if not api_cards:
                self.stdout.write(self.style.WARNING(f"  [{card_set.code}] no cards returned for tcgio_code={card_set.tcgio_code}"))
                continue

            # Map card_number -> set of marks seen, to detect genuine
            # within-set variation and report it clearly.
            number_to_marks = defaultdict(set)
            number_to_mark_single = {}
            unmatched_api_cards = []

            for c in api_cards:
                mark = c.get("regulationMark", "")
                num = parse_card_number(c.get("number", ""))
                if num is None:
                    unmatched_api_cards.append(c.get("number", "?"))
                    continue
                number_to_marks[num].add(mark)
                number_to_mark_single[num] = mark  # last-write is fine; checked for conflicts below

            distinct_marks_in_set = {m for marks in number_to_marks.values() for m in marks if m}
            if len(distinct_marks_in_set) > 1:
                mixed_mark_sets.append((card_set.code, sorted(distinct_marks_in_set)))

            db_products = list(
                PokemonProduct.objects.filter(card_set=card_set).exclude(card_number__isnull=True)
            )

            updated_this_set = 0
            unmatched_this_set = 0
            to_save = []

            for p in db_products:
                if p.card_number not in number_to_mark_single:
                    unmatched_this_set += 1
                    continue
                new_mark = number_to_mark_single[p.card_number]
                if new_mark and new_mark != p.regulation_mark:
                    p.regulation_mark = new_mark
                    to_save.append(p)
                    updated_this_set += 1

            total_unmatched += unmatched_this_set
            total_updated += updated_this_set

            marks_summary = ", ".join(f"{m}={sum(1 for v in number_to_mark_single.values() if v == m)}" for m in sorted(distinct_marks_in_set)) or "none found"
            self.stdout.write(
                f"  [{card_set.code}] {card_set.name}: {len(api_cards)} API cards, "
                f"marks seen: {marks_summary} | "
                f"{updated_this_set} product(s) would update, {unmatched_this_set} unmatched"
            )

            if not dry_run and to_save:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(to_save, ["regulation_mark"], batch_size=500)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{'Would update' if dry_run else 'Updated'} {total_updated} product(s) total. "
            f"{total_unmatched} product(s) had no matching API card number (review manually)."
        ))

        if mixed_mark_sets:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Sets with genuinely MIXED regulation marks within the same set:"))
            for code, marks in mixed_mark_sets:
                self.stdout.write(f"  [{code}] marks present: {marks}")
