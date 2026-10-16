"""
move_energies.py - PokeBulk SA

Energy cards were all dumped into the era Energies sets (MEE / SVE). This moves
each one into the set it was RELEASED WITH, so it appears on that set's
checklist (at the end). Decided with Michael, 2026-10-16:

  SVE #1-8   (plain)        -> SVI
  SVE #9-16  (plain)        -> SCR
  SVE #17-24 (plain)        -> BLK  + shared with WHT (released the same day)
  SVE Cosmos Holo #1-8      -> MEW  (151)
  SVE Cracked Ice Holo 9-16 -> SVP  (promo energies only)
  MEE #1-8   (plain)        -> MEG
  MEE 30th Celebration 9-16 -> 30C

Moved rows keep their id, price, stock, images and product id (so nightly
price sync, buying-invoice cost trace and stock all carry over). They get
card_number=None and number="<SVE|MEE>-<nnn>" so they sort after the numbered
cards (same handling as the Mew R/RGB trio). Shared sets are added through
`also_in_sets` (one row, one stock count, listed in both checklists).

Dry run by default:
  python manage.py move_energies --skip-checks
  python manage.py move_energies --apply --skip-checks
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import CardSet, PokemonProduct

# product id -> (home set, [shared sets])
MAP = {}
def _add(pids, home, shared=()):
    for p in pids:
        MAP[p] = (home, list(shared))

_add(range(475425, 475433), "SVI")                      # SVE plain 1-8
_add(range(578862, 578870), "SCR")                      # SVE plain 9-16
_add([645286, 645287, 645288, 645289, 645301, 645302, 645303, 645304], "BLK", ["WHT"])  # SVE plain 17-24
_add(range(517177, 517185), "MEW")                      # SVE Cosmos Holo 1-8
_add([599738, 599740, 599741, 599742, 599743, 599745, 599746, 599747], "SVP")           # Cracked Ice Holo 9-16
_add(range(656263, 656271), "MEG")                      # MEE plain 1-8
_add(range(713248, 713256), "30C")                      # MEE 30th Celebration 9-16


class Command(BaseCommand):
    help = "Move Energy cards from MEE/SVE into the set they were released with (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually move the rows")

    def handle(self, *args, **o):
        apply = o["apply"]
        needed = {h for h, _ in MAP.values()} | {s for _, ss in MAP.values() for s in ss}
        sets = {c.code: c for c in CardSet.objects.filter(code__in=needed)}
        missing = needed - set(sets)
        if missing:
            raise CommandError(f"These target sets don't exist in the database: {sorted(missing)}")

        rows = list(PokemonProduct.objects.select_related("card_set").filter(tcgcsv_product_id__in=list(MAP)))
        self.stdout.write(f"{len(rows)} rows matched {len(MAP)} Energy products "
                          f"({'APPLYING' if apply else 'DRY RUN'})\n")
        found = {r.tcgcsv_product_id for r in rows}
        absent = sorted(set(MAP) - found)
        if absent:
            self.stdout.write(f"  note: not in DB (skipped): {absent}")

        moved = 0
        with transaction.atomic():
            for r in sorted(rows, key=lambda x: (MAP[x.tcgcsv_product_id][0], x.tcgcsv_product_id, x.variant_override or "")):
                home, shared = MAP[r.tcgcsv_product_id]
                src = r.card_set.code if r.card_set else "-"
                num = r.card_number if r.card_number is not None else (r.number or "")
                try:
                    num_txt = f"{int(str(num).split('/')[0]):03d}"
                except ValueError:
                    num_txt = str(num)
                new_number = f"{src if src in ('SVE', 'MEE') else 'EN'}-{num_txt}"
                self.stdout.write(f"  {r.tcgcsv_product_id} {r.variant_override or 'N':<3} {r.name[:44]:<44} "
                                  f"{src} -> {home}{' + ' + ','.join(shared) if shared else ''}   number {new_number}")
                if not apply:
                    continue
                if r.card_set_id != sets[home].id or r.card_number is not None or r.number != new_number:
                    r.card_set = sets[home]
                    r.card_number = None
                    r.number = new_number
                    r.save(update_fields=["card_set", "card_number", "number", "updated_at"])
                if shared:
                    r.also_in_sets.set([sets[s] for s in shared])
                moved += 1
            if not apply:
                transaction.set_rollback(True)

        self.stdout.write(f"\n{'Moved' if apply else 'Would move'} {moved if apply else len(rows)} rows.")
        if apply:
            self.stdout.write("Next: regenerate the checklist data (generate_checklist_data) and push the frontend file.")
