# products/management/commands/fix_chase_rarity_reprints.py
#
# Michael, 2026-09-11: rebuilding Checklists' completion tiers around
# rarity (Broke Base/Base Set/Special Set Base = "core" rarities; Master
# Set/Full Master = core + chase rarities like Illustration Rare/Special
# Illustration Rare -- see products/completion.py) surfaced a data gap:
# some sets' alt-art "chase" reprints of an EX/Ultra Rare card were synced
# with the same rarity="ultra_rare" as the cheap normal print of the SAME
# card, instead of "special_illustration_rare". Confirmed live on Pitch
# Black (PBL): "Lurantis EX" exists twice -- card_number 4 at R9.30
# (rarity ultra_rare) and card_number 96 at R46.90 (rarity ultra_rare,
# same pokedex_number, ~5x the price) -- both currently look identical to
# the completion tier math, so Master Set/Full Master under-count and
# Broke Base/Base Set/Special Set Base over-count for affected sets.
#
# This is a best-guess auto-fix (Michael, 2026-09-11: "Best-guess auto-fix,
# you review after"), NOT a guaranteed-correct one -- it only catches the
# one pattern we have concrete evidence of (an ultra_rare card reappearing
# at a different card_number under the same pokedex_number, priced well
# above its cheapest print). It will not catch a plain (non-EX) Pokemon's
# Illustration Rare alt-art if that print was tagged some other rarity, or
# a chase card that doesn't have a cheaper sibling print in this set at
# all. Review the printed list (or the --apply run's output) in Django
# admin afterward.
#
# Within each set: group active rarity="ultra_rare" products by
# pokedex_number. When a pokedex_number has products across 2+ distinct
# card_numbers, treat the cheapest card_number as the genuine Ultra
# Rare/EX print and reclassify every pricier card_number sharing that
# pokedex_number to "special_illustration_rare".
#
# Defaults to a dry run -- prints what it WOULD change, touches nothing.
# Pass --apply to actually save.
#
# Usage:
#   python manage.py fix_chase_rarity_reprints                # dry run, every set
#   python manage.py fix_chase_rarity_reprints --set PBL       # dry run, one set
#   python manage.py fix_chase_rarity_reprints --set PBL --apply

from collections import defaultdict

from django.core.management.base import BaseCommand

from products.models import CardSet, PokemonProduct


class Command(BaseCommand):
    help = "Best-guess reclassification of Ultra Rare alt-art reprints to Special Illustration Rare (see module docstring)."

    def add_arguments(self, parser):
        parser.add_argument("--set", dest="set_code", type=str, default=None, help="Only this set's code (e.g. PBL). Default: every set.")
        parser.add_argument("--apply", action="store_true", default=False, help="Actually save changes. Without this, only prints what would change.")

    def handle(self, *args, **options):
        set_code = options.get("set_code")
        apply_changes = options.get("apply")

        sets = CardSet.objects.filter(code=set_code) if set_code else CardSet.objects.all()
        if set_code and not sets.exists():
            self.stdout.write(self.style.ERROR(f"No set found with code {set_code!r}"))
            return

        total_flagged = 0

        for card_set in sets.order_by("code"):
            products = list(
                PokemonProduct.objects
                .filter(card_set=card_set, is_active=True, rarity="ultra_rare")
                .exclude(pokedex_number__isnull=True)
                .order_by("card_number")
            )
            if not products:
                continue

            by_pokedex = defaultdict(list)
            for p in products:
                by_pokedex[p.pokedex_number].append(p)

            set_flagged = []
            for pokedex_number, rows in by_pokedex.items():
                distinct_card_numbers = {r.card_number for r in rows}
                if len(distinct_card_numbers) < 2:
                    continue  # only one print at this pokedex_number under ultra_rare -- nothing to split

                # Group by card_number first -- a card_number can legitimately
                # have multiple rows (one per print variant, e.g. N/H/RH of
                # the SAME print), that's normal and not a duplicate print.
                by_card_number = defaultdict(list)
                for r in rows:
                    by_card_number[r.card_number].append(r)

                cheapest_card_number = min(
                    by_card_number,
                    key=lambda cn: min((row.price or 0) for row in by_card_number[cn]),
                )
                for card_number, group_rows in by_card_number.items():
                    if card_number == cheapest_card_number:
                        continue
                    set_flagged.extend(group_rows)

            if not set_flagged:
                continue

            total_flagged += len(set_flagged)
            self.stdout.write(f"\n{card_set.code} -- {card_set.name}: {len(set_flagged)} product(s) flagged")
            for row in set_flagged:
                self.stdout.write(
                    f"  #{row.card_number:<4} {row.name:<30} pokedex={row.pokedex_number!s:<5} "
                    f"price=R{row.price!s:<8} variant={row.variant_override or 'N':<6} "
                    f"ultra_rare -> special_illustration_rare"
                )
                if apply_changes:
                    row.rarity = "special_illustration_rare"

            if apply_changes:
                PokemonProduct.objects.bulk_update(set_flagged, ["rarity"])

        if total_flagged == 0:
            self.stdout.write(self.style.SUCCESS("No mispriced Ultra Rare duplicates found."))
        elif apply_changes:
            self.stdout.write(self.style.SUCCESS(f"\nApplied: reclassified {total_flagged} product(s) to Special Illustration Rare."))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nDry run -- {total_flagged} product(s) would be reclassified. "
                f"Re-run with --set CODE first to check one set, then --apply to save."
            ))
