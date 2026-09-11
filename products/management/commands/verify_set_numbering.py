# products/management/commands/verify_set_numbering.py
#
# Michael, 2026-09-11: "we need to find a definite way of defining the
# numbering of every set! Does tcgcsv have the number of all the set,
# showing the card number, then the /0** number?"
#
# Short answer: yes -- TCGCSV mirrors TCGplayer's own catalog, and every
# card product there carries an extendedData entry
#   {"name": "Number", "displayName": "Card Number", "value": "089/088"}
# in exactly the "NNN/TTT" format Michael's asking about, TTT being the
# set's official printed card count and NNN the card's own number
# (confirmed live against Ascended Heroes -- "001/217" through "049/217"
# in the raw TCGCSV response, matching this DB's own products.number
# field exactly).
#
# We already consume this. products/management/commands/rebuild_from_tcgcsv.py
# reads card["_number"] (the same TCGCSV Number string) for every product,
# and get_set_card_map() in products/completion.py already keys off
# PokemonProduct.number for its numbered/unnumbered split whenever it's
# populated. So the raw ground truth Michael's asking for is already
# sitting in this DB, on every card.
#
# The gap: CardSet.total_cards -- the value completion.py falls back to
# when a card's own `number` is blank, and the value every "numbered vs
# unnumbered" decision ultimately compares card_number against -- is NOT
# derived from that same TCGCSV Number string. It's set independently by
# import_card.py/import_set.py from a totally different source
# (set_data.get('total', 0), a pokemontcg.io-style set schema), and
# rebuild_from_tcgcsv.py's norm_number() throws the "/TTT" denominator
# away entirely when stamping tcgcsv_product_id onto existing rows or
# creating new ones. Nothing in this codebase currently cross-checks that
# CardSet.total_cards agrees with what every card's own `number` string
# says the set's denominator actually is.
#
# This command is that cross-check -- the "definite way of defining the
# numbering of every set" Michael asked for, built entirely from data
# already in this DB (no live TCGCSV fetch needed, since we already
# synced it):
#
#   For every CardSet, look at every active PokemonProduct.number that's
#   populated and parse its "NNN/TTT" denominator. Report:
#     - MISSING_TOTAL_CARDS: total_cards is 0/unset but cards do carry a
#       consistent denominator we could backfill from.
#     - MISMATCH: total_cards disagrees with the denominator the cards
#       themselves carry (the strongest signal something's wrong).
#     - SPLIT_DENOMINATORS: a set's own cards disagree with EACH OTHER
#       (more than one distinct denominator seen). NOT necessarily a bug
#       -- Trick or Trade/TorT sets legitimately carry each reprinted
#       card's ORIGINAL set's denominator (see completion.py's note on
#       TT22's Mewtwo "056/172" vs Haunter "056/198"), so this is flagged
#       for review, not auto-fixed.
#     - NO_NUMBER_DATA: no active card in the set has `number` populated
#       at all -- nothing to cross-check against, total_cards is trusted
#       as-is.
#     - OK: total_cards agrees with the one consistent denominator seen.
#
# Defaults to report-only. --apply backfills MISSING_TOTAL_CARDS and
# MISMATCH sets to the majority (mode) denominator seen among their own
# cards -- never touches SPLIT_DENOMINATORS sets, those need a human look
# first (same "best-guess auto-fix, you review after" pattern as
# fix_chase_rarity_reprints.py).
#
# Usage:
#   python manage.py verify_set_numbering                # report, every set
#   python manage.py verify_set_numbering --set ASC      # report, one set
#   python manage.py verify_set_numbering --apply         # backfill safe cases

from collections import Counter

from django.core.management.base import BaseCommand

from products.models import CardSet, PokemonProduct


def parse_denominator(number: str) -> int | None:
    """'089/088' -> 88. Returns None for blank/malformed strings (TG01,
    SWSH001, or simply not populated)."""
    if not number or "/" not in number:
        return None
    denom = number.rsplit("/", 1)[-1].strip()
    if not denom.isdigit():
        return None
    return int(denom)


class Command(BaseCommand):
    help = "Cross-check CardSet.total_cards against the denominator every card's own `number` string already carries (sourced from TCGCSV's Number field)."

    def add_arguments(self, parser):
        parser.add_argument("--set", dest="set_code", type=str, default=None, help="Only this set's code (e.g. ASC). Default: every set.")
        parser.add_argument("--apply", action="store_true", default=False, help="Backfill MISSING_TOTAL_CARDS/MISMATCH sets to the mode denominator. Never touches SPLIT_DENOMINATORS sets.")

    def handle(self, *args, **options):
        set_code = options.get("set_code")
        apply_changes = options.get("apply")

        sets = CardSet.objects.filter(code=set_code) if set_code else CardSet.objects.all()
        if set_code and not sets.exists():
            self.stdout.write(self.style.ERROR(f"No set found with code {set_code!r}"))
            return

        counts = Counter()
        to_fix = []

        for card_set in sets.order_by("code"):
            denominators = Counter()
            for number in (
                PokemonProduct.objects
                .filter(card_set=card_set, is_active=True)
                .exclude(number="")
                .values_list("number", flat=True)
            ):
                denom = parse_denominator(number)
                if denom is not None:
                    denominators[denom] += 1

            if not denominators:
                counts["NO_NUMBER_DATA"] += 1
                continue

            distinct = list(denominators.keys())
            mode_denom, mode_count = denominators.most_common(1)[0]

            if len(distinct) > 1:
                counts["SPLIT_DENOMINATORS"] += 1
                self.stdout.write(self.style.WARNING(
                    f"SPLIT_DENOMINATORS  {card_set.code:10} total_cards={card_set.total_cards:<5} "
                    f"seen={dict(denominators)}  (mode={mode_denom}, {mode_count} cards) -- needs a human look"
                ))
                continue

            if card_set.total_cards == 0:
                counts["MISSING_TOTAL_CARDS"] += 1
                self.stdout.write(self.style.WARNING(
                    f"MISSING_TOTAL_CARDS {card_set.code:10} total_cards=0        -> {mode_denom} ({mode_count} cards agree)"
                ))
                to_fix.append((card_set, mode_denom))
            elif card_set.total_cards != mode_denom:
                counts["MISMATCH"] += 1
                self.stdout.write(self.style.ERROR(
                    f"MISMATCH            {card_set.code:10} total_cards={card_set.total_cards:<5} -> {mode_denom} ({mode_count} cards agree)"
                ))
                to_fix.append((card_set, mode_denom))
            else:
                counts["OK"] += 1

        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(
            f"OK:                  {counts['OK']}\n"
            f"MISMATCH:            {counts['MISMATCH']}\n"
            f"MISSING_TOTAL_CARDS: {counts['MISSING_TOTAL_CARDS']}\n"
            f"SPLIT_DENOMINATORS:  {counts['SPLIT_DENOMINATORS']} (never auto-fixed -- review manually)\n"
            f"NO_NUMBER_DATA:      {counts['NO_NUMBER_DATA']} (total_cards trusted as-is, nothing to cross-check)\n"
        )

        if not to_fix:
            self.stdout.write(self.style.SUCCESS("Nothing to fix."))
            return

        if apply_changes:
            for card_set, mode_denom in to_fix:
                card_set.total_cards = mode_denom
            CardSet.objects.bulk_update([cs for cs, _ in to_fix], ["total_cards"])
            self.stdout.write(self.style.SUCCESS(f"\nApplied: backfilled total_cards for {len(to_fix)} set(s)."))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nDry run -- {len(to_fix)} set(s) would be backfilled. Re-run with --apply to save."
            ))
