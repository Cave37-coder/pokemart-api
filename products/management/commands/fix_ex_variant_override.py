# products/management/commands/fix_ex_variant_override.py
#
# Michael, 2026-09-11: "you going to have to redo Pitch black checklist the
# EX cards are missing totally" -- root cause: get_set_card_map()
# (products/completion.py) and build_set_cards()
# (generate_checklist_data.py) both skip any row whose variant is not in
# FULL_VARIANTS = {N, H, RH, PB, MB, LB, FB, QB, UB, DB, TT, ESH}. Pitch
# Black's 10 base ex cards (Lurantis ex, Mega Delphox ex, Wailord ex,
# Mega Zeraora ex, Mega Slowbro ex, Mega Chandelure ex, Rampardos ex, Mega
# Darkrai ex, Morpeko ex, Mega Excadrill ex) were created by hand in Django
# admin with variant_override="HR-EX" -- not a real code, so they were
# silently dropped from BOTH the checklist grid AND live tier-completion
# tracking. Not Pitch Black-only: the same audit found Chaos Rising (CRI)
# has 23 more rows with the same problem (10 "EX" + 13 "HR-EX").
#
# Confirmed via live data every OTHER manually-or-TCGCSV-created single
# print row in these same sets -- rares, illustration rares, even other
# ultra_rare item cards -- consistently uses variant_override="H" for a
# card's one-and-only foil print. "EX"/"HR-EX" were just non-standard
# labels typed in ad hoc when these particular rows were added, not a
# deliberate different print type. This command normalizes them to "H" so
# they're tracked like every other chase card in the set.
#
# NOT touched: TR/SE/PBP/MBP/CC -- per products/completion.py's own
# comment, those are deliberately-excluded bonus-pull codes (promo stamps,
# code cards), not omissions. This command only ever touches variant_override
# values in TARGET_VALUES below.
#
# Defaults to dry-run. Pass --apply to save. --set CODE to scope to one set
# (omit to scan every set).
#
# Usage:
#   python manage.py fix_ex_variant_override                 # dry run, all sets
#   python manage.py fix_ex_variant_override --set PBL --apply
#   python manage.py fix_ex_variant_override --apply          # every affected set

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import CardSet, PokemonProduct

TARGET_VALUES = {"EX", "HR-EX"}
NEW_VARIANT = "H"


class Command(BaseCommand):
    help = "Normalize non-standard 'EX'/'HR-EX' variant_override values to 'H' so those rows aren't silently dropped from checklist/completion tracking."

    def add_arguments(self, parser):
        parser.add_argument("--set", type=str, default=None, help="CardSet.code to scope to. Omit to scan every set.")
        parser.add_argument("--apply", action="store_true", default=False, help="Actually save changes. Without this, only prints what would change.")

    def handle(self, *args, **options):
        set_code = options["set"]
        apply_changes = options["apply"]

        qs = PokemonProduct.objects.filter(is_active=True, variant_override__in=TARGET_VALUES)
        if set_code:
            try:
                card_set = CardSet.objects.get(code=set_code)
            except CardSet.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"No CardSet found with code {set_code!r}"))
                return
            qs = qs.filter(card_set=card_set)

        rows = list(qs.select_related("card_set"))
        if not rows:
            self.stdout.write(self.style.SUCCESS("No rows with a non-standard EX/HR-EX variant found -- nothing to do."))
            return

        by_set = defaultdict(list)
        for p in rows:
            by_set[p.card_set.code].append(p)

        # Guard: check for a pre-existing "H" row at the same (card_set, card_number)
        # -- would mean this card already has a distinct H print, so blindly
        # renaming would create a genuine collision that needs a human look
        # rather than a silent overwrite.
        collisions = []
        clean = []
        for code, set_rows in by_set.items():
            existing_h = set(
                PokemonProduct.objects.filter(
                    card_set__code=code, is_active=True, variant_override="H"
                ).values_list("card_number", flat=True)
            )
            for p in set_rows:
                if p.card_number in existing_h:
                    collisions.append(p)
                else:
                    clean.append(p)

        if collisions:
            self.stdout.write(self.style.WARNING(f"{len(collisions)} row(s) skipped -- an 'H' row already exists at the same card_number (needs a manual look, not auto-renamed):"))
            for p in collisions:
                self.stdout.write(f"  {p.card_set.code} #{p.card_number} {p.name} ({p.pb_id}, currently '{p.variant_override}')")
            self.stdout.write("")

        if not clean:
            self.stdout.write(self.style.SUCCESS("Nothing left to fix after the collision check."))
            return

        self.stdout.write(f"{len(clean)} row(s) will have variant_override changed '{{EX,HR-EX}}' -> '{NEW_VARIANT}':")
        for p in clean:
            self.stdout.write(f"  {p.card_set.code} #{p.card_number:<4} {p.name:<28} '{p.variant_override}' -> '{NEW_VARIANT}'  ({p.pb_id})")

        if not apply_changes:
            self.stdout.write(self.style.WARNING(f"\nDry run -- {len(clean)} row(s) would change. Re-run with --apply to save."))
            return

        with transaction.atomic():
            for p in clean:
                p.variant_override = NEW_VARIANT
                p.variant_sort = 1  # matches "H"'s sort position everywhere else in these sets
            PokemonProduct.objects.bulk_update(clean, ["variant_override", "variant_sort"])

        self.stdout.write(self.style.SUCCESS(f"\nApplied: updated {len(clean)} row(s)."))
