"""
mark_energy_numbers -- stop Energy cards clashing with Pokemon numbers on a set's checklist (2026-11-20).

Michael: "we need to mark the energies in the number so they don't clash with the set number -- there are a few sets
where 005 shows Pokemon and energy card next to each other!"

Finds every set (home cards + linked cards, exactly what the checklist shows) where an Energy card shares a display
number with a non-Energy card, and renames the Energy's `number` to "EN-<number>" (005 -> EN-005). card_number is left
alone, so tiers/ordering behave as before. Energies sort after the numbered cards (the generator already puts "EN-"
numbers last).

Customers' ticks survive: where a collision had split the tile into "005-<id>" keys, their ChecklistEntry rows are
re-keyed to the new keys (Pokemon back to plain "005", Energy to "EN-005").

    python manage.py mark_energy_numbers                 # DRY RUN: lists every clash + how many ticks would move
    python manage.py mark_energy_numbers --apply
    python manage.py mark_energy_numbers --set SMK1      # one set only
    python manage.py mark_energy_numbers --status
Then: python manage.py generate_checklist_data  and push the frontend file.
Progress: [i/total] per set, mark_energy_numbers_progress.txt.
"""
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from products.models import CardSet, PokemonProduct, ChecklistEntry
from products.management.commands.audit_energy import energy_kind
from products.management.commands.generate_checklist_data import (
    FULL_VARIANTS, fallback_display_num, is_promo_home, promo_display_num,
)

PROGRESS_FILE = "mark_energy_numbers_progress.txt"


def tile_keys(rows):
    """rows: list of dicts (id, name, variant, display). Returns {row id: key prefix} using the SAME rules as
    generate_checklist_data.build_set_cards / completion.get_set_card_map."""
    by_display = defaultdict(list)
    for r in rows:
        by_display[r["display"]].append(r)
    out = {}
    for display, rs in by_display.items():
        counts = Counter(r["variant"] for r in rs)
        genuine = any(c > 1 for c in counts.values())
        if not genuine:
            groups = {None: rs}
        else:
            groups = defaultdict(list)
            for r in rs:
                groups[r["name"]].append(r)
        for _name, g in groups.items():
            key = display if len(groups) == 1 else f"{display}-{min(x['id'] for x in g)}"
            for r in g:
                out[r["id"]] = key
    return out


class Command(BaseCommand):
    help = "Prefix clashing Energy numbers with EN- (dry run unless --apply); re-keys customers' checklist ticks."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--set", default="")
        parser.add_argument("--status", action="store_true")

    def handle(self, *args, **o):
        if o["status"]:
            self.stdout.write(open(PROGRESS_FILE, encoding="utf-8").read() if os.path.exists(PROGRESS_FILE) else "No run yet.")
            return
        apply = o["apply"]
        sets = CardSet.objects.all().order_by("code")
        if o["set"]:
            sets = sets.filter(code__iexact=o["set"])
        sets = list(sets)
        total = len(sets)
        self.stdout.write(f"{'APPLYING' if apply else 'DRY RUN'} -- {total} set(s)\n")

        tot_sets = tot_cards = tot_ticks = 0
        for i, cs in enumerate(sets, 1):
            line = f"[{i}/{total}] {100 * i // max(total, 1):>3}%  {cs.code}"
            if i % 10 == 0 or i == total:
                with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                    f.write(f"mark_energy_numbers {datetime.now():%Y-%m-%d %H:%M:%S} ({'APPLY' if apply else 'DRY RUN'})\n{line}\n")
            qs = (PokemonProduct.objects
                  .filter(Q(card_set=cs) | Q(id__in=cs.shared_products.values("id")), is_active=True)
                  .values("id", "card_number", "variant_override", "number", "name", "card_set_id", "card_set__code"))
            rows = []
            for p in qs:
                variant = p["variant_override"] or "N"
                if variant not in FULL_VARIANTS:
                    continue
                raw = (p["number"] or "").strip()
                if not raw and p["card_number"] is None:
                    continue
                display = raw or fallback_display_num(p["card_number"], cs.total_cards or 0)
                if p["card_set_id"] != cs.id and is_promo_home(p["card_set__code"]):
                    display = promo_display_num(raw, p["card_number"])
                rows.append({"id": p["id"], "name": p["name"], "variant": variant, "display": display,
                             "energy": bool(energy_kind(p["name"]))})
            by_display = defaultdict(list)
            for r in rows:
                by_display[r["display"]].append(r)
            clashes = {d: rs for d, rs in by_display.items()
                       if any(r["energy"] for r in rs) and any(not r["energy"] for r in rs) and not d.startswith("EN-")}
            if not clashes:
                continue

            before = tile_keys(rows)
            renamed = {}   # row id -> new number
            for d, rs in clashes.items():
                base = d.split("/")[0]
                for r in rs:
                    if r["energy"]:
                        renamed[r["id"]] = f"EN-{base}"
            after_rows = [dict(r, display=renamed.get(r["id"], r["display"])) for r in rows]
            after = tile_keys(after_rows)

            moves = []   # (old key, new key) per variant
            for r in rows:
                if before[r["id"]] != after[r["id"]]:
                    moves.append((f"{before[r['id']]}_{r['variant']}", f"{after[r['id']]}_{r['variant']}"))
            ticks = ChecklistEntry.objects.filter(card_set=cs.code, card_key__in=[m[0] for m in moves]).count() if moves else 0

            tot_sets += 1
            tot_cards += len(renamed)
            tot_ticks += ticks
            ex = ", ".join(f"{d}: {', '.join(sorted({r['name'][:22] for r in rs if r['energy']}))[:40]}" for d, rs in list(clashes.items())[:3])
            self.stdout.write(f"{line:22} {len(clashes)} clashing number(s), {len(renamed)} Energy row(s) -> EN-, {ticks} tick(s) to re-key   e.g. {ex}")

            if not apply:
                continue
            with transaction.atomic():
                for rid, new in renamed.items():
                    PokemonProduct.objects.filter(pk=rid).update(number=new)
                for old, new in moves:
                    if old == new:
                        continue
                    for ce in ChecklistEntry.objects.filter(card_set=cs.code, card_key=old):
                        # don't collide with a row the same user already has under the new key
                        if ChecklistEntry.objects.filter(user=ce.user, card_set=cs.code, card_key=new).exists():
                            ce.delete()
                        else:
                            ce.card_key = new
                            ce.save(update_fields=["card_key"])

        self.stdout.write(f"\n{tot_sets} set(s) with clashes | {tot_cards} Energy row(s) renamed | {tot_ticks} tick(s) re-keyed.")
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run -- nothing written. Add --apply to do it."))
        else:
            self.stdout.write("Next: python manage.py generate_checklist_data, then push the frontend checklist file.")
