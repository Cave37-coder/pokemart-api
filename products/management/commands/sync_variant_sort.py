# products/management/commands/sync_variant_sort.py
#
# Michael, 2026-09-29: "the cards aren't all in the correct sequence of
# variant, First must be Normal or Holo then only the Rev Holo after, for
# some reason the Rev Holo shows before the Holo!!"
#
# ROOT CAUSE: PokemonProduct.variant_sort is only ever SET at the moment a
# row is created by sync_tcgcsv.py (or corrected via the manage_set admin
# tool's "apply variant" action -- also just fixed today to keep
# variant_sort in sync going forward). Any row whose variant_sort was never
# touched by either of those two paths -- most commonly rows created before
# variant_sort existed at all, or rows whose variant was corrected through
# the admin tool BEFORE today's fix -- kept the model's bare default of 9.
# Since Holo (H) correctly sorts at 1 and Reverse Holo (RH) at 2, a Holo row
# stuck on the default of 9 sorts AFTER its own Rev Holo sibling (2 < 9) --
# exactly backwards from what Michael's seeing.
#
# This is a deterministic fix, not a fuzzy match like the pokedex_number
# backfill: variant_sort is a pure function of variant_override via
# PokemonProduct.VARIANT_SORT_ORDER (see that constant's own comment in
# products/models.py). So this command doesn't need a "no match" bucket --
# every active row either already has the right value (left alone) or gets
# recomputed to it.
#
# SAFE BY DESIGN: only ever touches variant_sort, never variant_override
# itself, and only rows where the recomputed value actually differs from
# what's stored -- re-running this after another sync_tcgcsv run only
# touches whatever's newly wrong (should normally be zero rows, since
# sync_tcgcsv now sets it correctly at creation time; this is the one-off
# catch-up for everything created/edited before today).
#
# Usage:
#   python manage.py sync_variant_sort            # dry run, prints every fix
#   python manage.py sync_variant_sort --apply     # writes to the DB

from django.core.management.base import BaseCommand

from products.models import PokemonProduct


class Command(BaseCommand):
    help = (
        "Recompute variant_sort for every active product from its variant_override "
        "(N < H < RH < ... per PokemonProduct.VARIANT_SORT_ORDER), fixing rows left "
        "with a stale/default value so Rev Holo etc. no longer sorts ahead of Holo. "
        "Only ever changes variant_sort; never touches variant_override itself."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes to the DB. Without this, dry-run only.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        products = list(
            PokemonProduct.objects.filter(is_active=True)
            .select_related("card_set")
            .only("id", "name", "variant_override", "variant_sort", "card_set__code")
        )
        self.stdout.write(f"Checking {len(products)} active products.\n")

        to_fix = []  # (product, old_sort, new_sort)
        unknown_variant = []  # variant_override not in VARIANT_SORT_ORDER at all (still defaults to 9 -- flagged, not "wrong")

        for p in products:
            correct = PokemonProduct.VARIANT_SORT_ORDER.get(p.variant_override, 9)
            if p.variant_override and p.variant_override not in PokemonProduct.VARIANT_SORT_ORDER:
                unknown_variant.append(p)
            if p.variant_sort != correct:
                to_fix.append((p, p.variant_sort, correct))

        self.stdout.write(self.style.SUCCESS(f"TO FIX: {len(to_fix)} rows have a stale variant_sort"))
        self.stdout.write(f"--- Sample of fixes (first 60 of {len(to_fix)}) ---")
        for p, old, new in to_fix[:60]:
            set_code = p.card_set.code if p.card_set else "?"
            self.stdout.write(
                f"  id={p.id} {p.name!r} [{set_code}] variant={p.variant_override!r} "
                f"variant_sort {old} -> {new}"
            )

        if unknown_variant:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(unknown_variant)} rows have a variant_override that isn't in "
                    f"VARIANT_SORT_ORDER at all (falls back to 9, same as before -- these "
                    f"aren't being made worse, just flagged in case one is a typo):"
                )
            )
            seen_variants = {}
            for p in unknown_variant:
                seen_variants.setdefault(p.variant_override, []).append(p)
            for variant, rows in list(seen_variants.items())[:20]:
                self.stdout.write(f"  variant_override={variant!r}: {len(rows)} row(s), e.g. id={rows[0].id} {rows[0].name!r}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN -- nothing written. Review the fixes above, then rerun with "
                f"--apply to write {len(to_fix)} rows."
            ))
            return

        to_update = []
        for p, old, new in to_fix:
            p.variant_sort = new
            to_update.append(p)

        PokemonProduct.objects.bulk_update(to_update, ["variant_sort"], batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"\nApplied: {len(to_update)} products corrected."))
