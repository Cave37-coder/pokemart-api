"""
link_promos_to_sets -- PokeBulk SA

Links promo cards (SVP, MEP, SMP, PR-* ...) to the main set they belong to, so they show on that set's checklist
(Full Master / Complete tier) -- see products/promo_links.py. A link is just promo.also_in_sets += main set.

AUTOMATIC rule (safe, exact): a promo whose NAME carries a printed "n/total" (e.g. "Arcanine - 012/099 (Prerelease)
[Staff]") belongs to the ONE set that has printed total `total` and a card number `n` with the same card name.
Anything else is linked by hand: Django admin > Pokemon products > select the promos > action
"Link selected promos to a set".

  python manage.py link_promos_to_sets            # dry run (prints what it would link)
  python manage.py link_promos_to_sets --apply
  python manage.py link_promos_to_sets --unlink-all --apply   # undo every promo link made by this tool
After linking, regenerate checklistData.ts (generate_checklist_data) and push it.
"""
import re
from collections import defaultdict

from django.core.management.base import BaseCommand

from products.models import CardSet, PokemonProduct
from products.promo_links import PROMO_HOME_PREFIXES, is_promo_home

NUMTOT = re.compile(r"(\d+)\s*/\s*(\d+)")


def base_name(n):
    n = re.sub(r"\s*[\(\[].*$", "", n or "")
    n = re.sub(r"\s+-\s+\S*\d.*$", "", n)
    return n.strip().lower()


class Command(BaseCommand):
    help = "Link promo cards to the main set they belong to (shows on that set's checklist)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--unlink-all", action="store_true", help="Remove every link from a promo set into another set")

    def handle(self, *args, **o):
        apply = o["apply"]
        promos = [p for p in PokemonProduct.objects.filter(is_active=True).select_related("card_set")
                  if p.card_set and is_promo_home(p.card_set.code)]

        if o["unlink_all"]:
            n = 0
            for p in promos:
                links = list(p.also_in_sets.all())
                if links:
                    n += len(links)
                    if apply:
                        p.also_in_sets.clear()
            self.stdout.write(f"{'Removed' if apply else 'Would remove'} {n} link(s).")
            return

        # (printed total) -> {set code: {(card_number, base name)}}
        by_total = defaultdict(lambda: defaultdict(set))
        sets = {s.code: s for s in CardSet.objects.all()}
        for p in PokemonProduct.objects.filter(is_active=True, card_set__isnull=False).exclude(card_number=None).select_related("card_set"):
            code = p.card_set.code
            if is_promo_home(code) or not p.card_set.total_cards:
                continue
            by_total[p.card_set.total_cards][code].add((p.card_number, base_name(p.name)))

        linked = skipped = already = 0
        per_set = defaultdict(int)
        for p in promos:
            m = NUMTOT.search(p.name or "")
            if not m:
                skipped += 1
                continue
            num, tot = int(m.group(1)), int(m.group(2))
            cands = [c for c, cards in by_total.get(tot, {}).items() if (num, base_name(p.name)) in cards]
            if len(cands) != 1:
                skipped += 1
                continue
            target = sets[cands[0]]
            if p.also_in_sets.filter(pk=target.pk).exists():
                already += 1
                continue
            per_set[target.code] += 1
            linked += 1
            self.stdout.write(f"  {p.card_set.code}: {p.name}  ->  {target.code}")
            if apply:
                p.also_in_sets.add(target)

        self.stdout.write(self.style.SUCCESS(
            f"{'Linked' if apply else 'Would link'} {linked} promo(s); {already} already linked; {skipped} have no safe automatic match "
            f"(link those in admin)."))
        if per_set:
            self.stdout.write("Per set: " + ", ".join(f"{c}({n})" for c, n in sorted(per_set.items(), key=lambda x: -x[1])))
        if not apply:
            self.stdout.write("Dry run -- add --apply to write.")
