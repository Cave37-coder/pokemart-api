"""
Computes PokemonProduct.legal_expanded for the whole catalog.

Expanded format rule (structurally different from Standard): every
individual printing from the Black & White era (2011) onward is
independently Expanded-legal, based purely on which set/era it was
printed in -- there is NO regulation-mark system and NO Trainer reprint
pass-through for Expanded the way there is for Standard. A card printed
before BW is simply not Expanded-legal at all, even if a later BW+
printing of the same card exists (that later printing is independently
legal on its own, unaffected by the older one).

KNOWN LIMITATION -- NOT IMPLEMENTED: the real Expanded format also has a
ban list (specific Trainer/Item cards banned outright, e.g. certain draw
Supporters and Energy-acceleration Items). This command marks every BW+
printing as legal_expanded=True regardless of ban status. Guessing at an
unverified ban list would produce confidently wrong data, which is worse
than a clearly-flagged gap -- if/when the actual current ban list is
sourced and verified, this command should be extended to exclude those
specific cards.

Usage:
    python manage.py compute_expanded_legality --dry-run
    python manage.py compute_expanded_legality
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import PokemonProduct

# Black & White onward. Matches this codebase's existing ERA_ORDER/Era.code
# conventions (BW, XY, SM, SWSH, SV, MEG) -- PLUS the parallel promo/special
# era buckets B4-B8 (confirmed 2026-06-20 via Era.name: B4="Black & White
# Era", B5="XY Era", B6="Sun & Moon Era", B7="Sword & Shield Era",
# B8="Scarlet & Violet Era" -- these mirror the main eras under different
# codes, used for promo/McDonald's/Trainer Kit/etc sets). B1-B3 (WotC Base/
# EX/Diamond & Pearl-equivalent) are correctly excluded, matching their main
# era counterparts. PRIZE (Prize Pack Series) and TOT (Trick or Trade) are
# included based on their confirmed release dates all falling in 2022-2025,
# well within the SWSH/SV timeframe.
EXPANDED_LEGAL_ERA_CODES = {
    'BW', 'XY', 'SM', 'SWSH', 'SV', 'MEG',
    'B4', 'B5', 'B6', 'B7', 'B8',
    'PRIZE', 'TOT',
}


class Command(BaseCommand):
    help = "Recompute legal_expanded for every product (BW-era onward, era-cutoff only -- no ban list)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        products = list(
            PokemonProduct.objects.select_related('card_set__era')
            .only('id', 'legal_expanded', 'card_set__era__code')
        )
        self.stdout.write(f"Loaded {len(products)} product(s).")

        to_update = []
        becoming_legal = 0
        becoming_illegal = 0
        unchanged = 0

        for p in products:
            era_code = p.card_set.era.code if (p.card_set and p.card_set.era) else None
            target = era_code in EXPANDED_LEGAL_ERA_CODES
            if target != p.legal_expanded:
                if target:
                    becoming_legal += 1
                else:
                    becoming_illegal += 1
                p.legal_expanded = target
                to_update.append(p)
            else:
                unchanged += 1

        self.stdout.write("")
        self.stdout.write(f"Would change: {len(to_update)} product(s)")
        self.stdout.write(f"  -> becoming legal_expanded=True:  {becoming_legal}")
        self.stdout.write(f"  -> becoming legal_expanded=False: {becoming_illegal}")
        self.stdout.write(f"Unchanged: {unchanged} product(s)")

        if dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Dry run -- no changes saved. Ban list NOT applied (see module docstring)."))
            return

        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, ['legal_expanded'], batch_size=500)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Saved. Updated {len(to_update)} product(s). Ban list NOT applied (see module docstring)."))
