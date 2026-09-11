# products/management/commands/fix_pbl_ex_duplicates.py
#
# Michael, 2026-09-11: running fix_ex_variant_override --set PBL correctly
# refused to rename the 10 base ex cards' variant_override, because by the
# time it ran, a SECOND, separate row for each of those same 10 cards had
# already been created (via `sync_tcgcsv --set-code PBL`, run in between --
# now that PBL is in sync_tcgcsv's GROUP_CONFIG). Confirmed live: each of
# the 10 card numbers (4, 8, 16, 27, 31, 38, 45, 48, 55, 65) now has TWO
# active rows --
#   - the OLD one, hand-created in admin before TCGCSV had these cards,
#     pb_id "PB-MEG-PBL-<pokedex>-HR-EX-<num>", variant_override "HR-EX"
#     (the one the earlier fix targeted).
#   - a NEW one sync_tcgcsv just created, pb_id "PBL-<num>-H",
#     variant_override "H" (correctly recognised) and rarity "double_rare"
#     (correctly synced -- confirms both earlier fixes worked). But its
#     pb_id doesn't match the "TCGCSV-<productId>..." pattern the checklist
#     page's Buy-button matching relies on (see the fix in sync_tcgcsv.py's
#     pb_id generation, same session) -- so as created, it would show up
#     but Buy wouldn't work.
#
# This command resolves both problems for exactly these 10 cards:
#   1. Deactivates the OLD hand-created row (is_active=False, not deleted --
#      preserves it for any historical order it might already be on).
#   2. Rewrites the NEW row's pb_id to "TCGCSV-<productId>-H", using the
#      real TCGCSV productId for each card (confirmed 2026-09-11 against
#      https://tcgcsv.com/tcgplayer/3/24688/products -- hardcoded below
#      since it's fixed, known data, not something to re-derive live).
#
# Defaults to dry-run. Pass --apply to save.
#
# Usage:
#   python manage.py fix_pbl_ex_duplicates
#   python manage.py fix_pbl_ex_duplicates --apply

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import PokemonProduct

SET_CODE = "PBL"

# card_number -> real TCGCSV productId (from the Double Rare print of each
# card, confirmed against tcgcsv.com/tcgplayer/3/24688/products).
CARD_NUMBER_TO_TCGCSV_ID = {
    4: 704761,
    8: 704765,
    16: 704773,
    27: 704784,
    31: 704788,
    38: 704795,
    45: 704802,
    48: 704805,
    55: 704812,
    65: 704822,
}


class Command(BaseCommand):
    help = "Deactivate the 10 hand-created duplicate PBL ex-card rows and fix the new sync_tcgcsv rows' pb_id to the TCGCSV-<id> convention."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False, help="Actually save changes. Without this, only prints what would change.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        rows = list(PokemonProduct.objects.filter(
            card_set__code=SET_CODE, is_active=True, card_number__in=CARD_NUMBER_TO_TCGCSV_ID.keys()
        ))

        actions = []
        for cn, tcgcsv_id in CARD_NUMBER_TO_TCGCSV_ID.items():
            at_number = [p for p in rows if p.card_number == cn]
            old = next((p for p in at_number if p.pb_id.startswith("PB-MEG-PBL-")), None)
            new = next((p for p in at_number if p.pb_id.startswith(f"{SET_CODE}-") and not p.pb_id.startswith("TCGCSV-")), None)

            if not old and not new:
                self.stdout.write(f"#{cn}: nothing to do (no old/new pair found -- may already be fixed).")
                continue
            if old and not new:
                self.stdout.write(self.style.WARNING(f"#{cn}: found the old hand-created row ({old.pb_id}) but no new sync_tcgcsv row -- leaving alone, nothing to deactivate against."))
                continue
            if new and not old:
                self.stdout.write(f"#{cn}: no old duplicate to deactivate, just fixing pb_id on {new.pb_id}.")

            new_pb_id = f"TCGCSV-{tcgcsv_id}-H"
            actions.append({"cn": cn, "old": old, "new": new, "new_pb_id": new_pb_id})

        if not actions:
            self.stdout.write(self.style.SUCCESS("Nothing to fix."))
            return

        self.stdout.write(f"\n{len(actions)} card(s) to fix:")
        for a in actions:
            if a["old"]:
                self.stdout.write(f"  #{a['cn']:<4} deactivate {a['old'].pb_id} (id={a['old'].id}, price={a['old'].price})")
            if a["new"]:
                self.stdout.write(f"  #{a['cn']:<4} relink     {a['new'].pb_id} -> {a['new_pb_id']} (id={a['new'].id}, price={a['new'].price})")

        if not apply_changes:
            self.stdout.write(self.style.WARNING(f"\nDry run -- re-run with --apply to save."))
            return

        with transaction.atomic():
            for a in actions:
                if a["old"]:
                    a["old"].is_active = False
                    a["old"].save(update_fields=["is_active"])
                if a["new"]:
                    a["new"].pb_id = a["new_pb_id"]
                    a["new"].save(update_fields=["pb_id"])

        self.stdout.write(self.style.SUCCESS(f"\nApplied: fixed {len(actions)} card(s)."))
