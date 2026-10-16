"""
energy_home_sets.py - PokeBulk SA (read-only)

Energy cards were never written to the set they were released with -- they
all sit in the era "Energies" sets (MEE = Mega Evolution Energies,
SVE = Scarlet & Violet Energies). This prints every Energy row in those
sets as one editable line, so each can be given its HOME SET:

    product_id | pattern | #   | type       | current set | -> HOME SET

HOME SET is pre-filled only where it is certain from the TCGplayer name
("(30th Celebration)" -> 30C). Everything else is left as ?? for Michael to
fill in (e.g. "SVI", "MEW", "SFA", "ASC"). The completed list is what the
move command will use (nothing is moved by this command).

  python manage.py energy_home_sets --skip-checks
"""
import re
from collections import OrderedDict

from django.core.management.base import BaseCommand

from products.models import PokemonProduct

ENERGY_SETS = ["MEE", "SVE"]
TYPES = ["Grass", "Fire", "Water", "Lightning", "Psychic", "Fighting", "Darkness", "Metal"]


def pattern_of(name):
    m = re.search(r"\(([^)]+)\)", name)
    return m.group(1) if m else "plain"


def type_of(name):
    for t in TYPES:
        if t.lower() in name.lower():
            return t
    return "?"


def suggest(name):
    if "(30th Celebration)" in name:
        return "30C"
    return "??"


class Command(BaseCommand):
    help = "Read-only: list Energy rows in the era Energy sets so each can be assigned its home set."

    def handle(self, *args, **o):
        rows = (PokemonProduct.objects.select_related("card_set")
                .filter(card_set__code__in=ENERGY_SETS, condition="NM")
                .order_by("card_set__code", "tcgcsv_product_id", "variant_override"))
        groups = OrderedDict()
        for r in rows:
            key = (r.card_set.code, pattern_of(r.name))
            groups.setdefault(key, []).append(r)
        self.stdout.write(f"{rows.count()} Energy rows in {', '.join(ENERGY_SETS)} "
                          f"({len(groups)} pattern groups). Fill in the HOME SET after '->'.\n")
        for (code, pat), rs in groups.items():
            self.stdout.write(f"--- {code} / {pat}  ({len(rs)} rows) ---")
            for r in rs:
                self.stdout.write(
                    f"{r.tcgcsv_product_id or '-':>7} | {pat:<18} | #{str(r.card_number or r.number or '-'):<4} | "
                    f"{type_of(r.name):<9} | {r.variant_override or 'N':<3} | stock {r.stock:<3} | -> {suggest(r.name)}")
            self.stdout.write("")
