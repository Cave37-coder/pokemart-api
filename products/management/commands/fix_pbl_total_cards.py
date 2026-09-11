# products/management/commands/fix_pbl_total_cards.py
#
# Michael, 2026-09-11: Pitch Black's CardSet.total_cards is 194 in
# production -- not the real print run (084 per TCGCSV's own "NNN/084"
# numbering on every card), but an exact match for the number of active
# PokemonProduct rows in the set (194), which is how this almost certainly
# happened -- something derived total_cards from a row count instead of the
# actual set size.
#
# This matters beyond cosmetics: PBL's `number` field is blank on every
# row, so every checklist card key is generated as
# f"{card_number:03d}/{total_cards}" (see generate_checklist_data.py /
# products/completion.py's _fallback_display_num). With total_cards=194,
# every PBL key currently ends "/194" (e.g. "001/194_N") -- confirmed live
# on the leaderboard (176/194, 160/194, etc). Fixing total_cards to 84
# changes that denominator, which means any ChecklistEntry a customer
# already saved for PBL (card_key ending "/194...") stops matching the
# newly-generated keys (ending "/084...") and would silently look
# unchecked.
#
# Michael, 2026-09-11, confirmed via AskUserQuestion: "Fix it + migrate
# existing checkmarks" -- so this command does BOTH in one atomic
# transaction: corrects CardSet.total_cards AND rewrites every existing
# PBL ChecklistEntry.card_key from ".../194..." to ".../084..." so nobody's
# progress is lost. Does NOT touch SetCompletionEvent -- those are
# historical "you completed X on this date" records under whatever
# numbering existed at the time; they aren't re-validated against current
# completion state and don't reference total_cards directly, so there's
# nothing there that would go stale.
#
# Defaults to dry-run. Pass --apply to save.
#
# Usage:
#   python manage.py fix_pbl_total_cards               # dry run
#   python manage.py fix_pbl_total_cards --apply

import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import CardSet, ChecklistEntry

SET_CODE = "PBL"
OLD_TOTAL = 194
NEW_TOTAL = 84


class Command(BaseCommand):
    help = f"Correct {SET_CODE}'s total_cards ({OLD_TOTAL} -> {NEW_TOTAL}) and migrate existing ChecklistEntry keys to match."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False, help="Actually save changes. Without this, only prints what would change.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        try:
            card_set = CardSet.objects.get(code=SET_CODE)
        except CardSet.DoesNotExist:
            raise CommandError(f"No CardSet found with code {SET_CODE!r}")

        if card_set.total_cards != OLD_TOTAL:
            self.stdout.write(self.style.WARNING(
                f"{SET_CODE}.total_cards is currently {card_set.total_cards}, not the expected {OLD_TOTAL} -- "
                "someone may have already fixed this, or the data has moved on. Stopping without changes, "
                "double check before re-running."
            ))
            return

        old_suffix = f"/{OLD_TOTAL}"
        new_suffix = f"/{NEW_TOTAL}"
        # Only replace "/194" when it's acting as the denominator (immediately
        # followed by "_" for a plain key, or "-" for a collision-disambiguated
        # key) -- not a blind string replace.
        pattern = re.compile(re.escape(old_suffix) + r"(?=[_-])")

        entries = list(ChecklistEntry.objects.filter(card_set=SET_CODE))
        to_migrate = [e for e in entries if pattern.search(e.card_key)]
        already_new = [e for e in entries if new_suffix in e.card_key]

        self.stdout.write(f"{SET_CODE}: total_cards {OLD_TOTAL} -> {NEW_TOTAL}")
        self.stdout.write(f"ChecklistEntry rows for {SET_CODE}: {len(entries)} total, {len(to_migrate)} need key migration, {len(already_new)} already on the new format")

        if to_migrate:
            by_user = {}
            for e in to_migrate:
                by_user.setdefault(e.user_id, 0)
                by_user[e.user_id] += 1
            self.stdout.write(f"  Affects {len(by_user)} user(s), e.g.:")
            for e in to_migrate[:5]:
                new_key = pattern.sub(new_suffix, e.card_key)
                self.stdout.write(f"    user={e.user_id} {e.card_key} -> {new_key}")
            if len(to_migrate) > 5:
                self.stdout.write(f"    ... and {len(to_migrate) - 5} more")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("\nDry run -- re-run with --apply to save."))
            return

        with transaction.atomic():
            card_set.total_cards = NEW_TOTAL
            card_set.save(update_fields=["total_cards"])

            updated = []
            for e in to_migrate:
                e.card_key = pattern.sub(new_suffix, e.card_key)
                updated.append(e)
            # Guard against a migrated key colliding with a row that already
            # exists on the new format (would violate the unique constraint) --
            # bulk_update would raise IntegrityError in that case, which is the
            # right failure mode (needs a human look), not something to swallow.
            ChecklistEntry.objects.bulk_update(updated, ["card_key"])

        self.stdout.write(self.style.SUCCESS(
            f"\nApplied: {SET_CODE}.total_cards is now {NEW_TOTAL}, migrated {len(to_migrate)} ChecklistEntry row(s)."
        ))
