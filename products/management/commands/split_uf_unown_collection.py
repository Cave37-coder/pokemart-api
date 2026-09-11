# products/management/commands/split_uf_unown_collection.py
#
# Michael, 2026-09-11: verify_set_numbering flagged Unseen Forces (UF) as
# SPLIT_DENOMINATORS -- 195 active cards agree on total_cards=115 (the
# main numbered set), but 28 cards consistently carry their own "X/28"
# denominator. That's not noise: EX Unseen Forces (2005) really did ship
# with a secondary "Unown Collection" insert -- its own 28-card, 1/28
# numbered mini-set bundled inside UF packs. Same structural pattern as
# the modern Trainer Gallery / Galarian Gallery sub-blocks, which this DB
# already splits into their own CardSet rows (SITTG, ASRTG, LORTG, BRSTG).
# Michael confirmed, 2026-09-11: "Split into its own set" (recommended
# option), matching that existing precedent.
#
# WHAT THIS DOES:
#   - Creates CardSet "UFUC" ("Unseen Forces: Unown Collection"), same era
#     and release_date as UF, total_cards=28.
#   - Moves every active PokemonProduct currently under UF whose `number`
#     denominator is 28 over to card_set=UFUC. Nothing else about those
#     rows changes (card_number, variants, rarity, price, images all
#     preserved as-is).
#   - UF itself keeps total_cards=115 (already correct) and is left with
#     only its main 115-card numbered checklist plus whatever unnumbered
#     chase cards it has beyond that -- no longer contaminated by the
#     Unown Collection's own numbering.
#
# Defaults to dry-run (prints what it would do, touches nothing).
# Pass --apply to actually create the set and move the products.
#
# Usage:
#   python manage.py split_uf_unown_collection             # dry run
#   python manage.py split_uf_unown_collection --apply

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import CardSet, PokemonProduct

SOURCE_CODE = "UF"
TARGET_CODE = "UFUC"
TARGET_NAME = "Unseen Forces: Unown Collection"
TARGET_TOTAL_CARDS = 28


def denominator(number: str) -> int | None:
    if not number or "/" not in number:
        return None
    denom = number.rsplit("/", 1)[-1].strip()
    return int(denom) if denom.isdigit() else None


class Command(BaseCommand):
    help = "Split Unseen Forces' 28-card Unown Collection sub-block out into its own CardSet (UFUC), matching the SITTG/ASRTG/LORTG/BRSTG Trainer Gallery precedent."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False, help="Actually create the set and move products. Without this, only prints what would happen.")

    def handle(self, *args, **options):
        apply_changes = options.get("apply")

        try:
            source = CardSet.objects.get(code=SOURCE_CODE)
        except CardSet.DoesNotExist:
            raise CommandError(f"No set found with code {SOURCE_CODE!r}")

        if CardSet.objects.filter(code=TARGET_CODE).exists():
            self.stdout.write(self.style.WARNING(f"{TARGET_CODE} already exists -- assuming this was already run."))
            target = CardSet.objects.get(code=TARGET_CODE)
        else:
            target = None

        to_move = [
            p for p in PokemonProduct.objects.filter(card_set=source, is_active=True)
            if denominator(p.number) == TARGET_TOTAL_CARDS
        ]

        if not to_move:
            self.stdout.write(self.style.SUCCESS(f"No active {SOURCE_CODE} products with an X/{TARGET_TOTAL_CARDS} number found -- nothing to move."))
            return

        self.stdout.write(f"Found {len(to_move)} product(s) in {SOURCE_CODE} to move to {TARGET_CODE}:")
        for p in to_move[:10]:
            card_num = str(p.card_number) if p.card_number is not None else "?"
            self.stdout.write(f"  #{card_num:<4} {p.name:<30} number={p.number}")
        if len(to_move) > 10:
            self.stdout.write(f"  ... and {len(to_move) - 10} more")

        if not apply_changes:
            self.stdout.write(self.style.WARNING(f"\nDry run -- {len(to_move)} product(s) would move from {SOURCE_CODE} to a new/existing {TARGET_CODE} set. Re-run with --apply to save."))
            return

        with transaction.atomic():
            if target is None:
                target = CardSet.objects.create(
                    code=TARGET_CODE,
                    name=TARGET_NAME,
                    era=source.era,
                    total_cards=TARGET_TOTAL_CARDS,
                    release_date=source.release_date,
                )
                self.stdout.write(self.style.SUCCESS(f"Created {TARGET_CODE} -- {TARGET_NAME}"))

            for p in to_move:
                p.card_set = target
            PokemonProduct.objects.bulk_update(to_move, ["card_set"])

        self.stdout.write(self.style.SUCCESS(f"\nApplied: moved {len(to_move)} product(s) from {SOURCE_CODE} to {TARGET_CODE}."))
