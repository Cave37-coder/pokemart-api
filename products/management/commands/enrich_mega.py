"""
enrich_mega.py - PokeBulk SA

One-shot Mega-era enrichment (Michael, 2026-10-07: "concentrate on Mega Era,
huge holes there"). Runs, in order:
  1. coverage report (before)
  2. enrich_bulbapedia  (HP, types, costs, attacks 1-3, abilities 1-2, stage,
                         evolves from, Japanese name, artist, dex)
  3. enrich_serebii     (fill-only gap filler)
  4. evolves_to derivation (from other cards' evolves_from)
  5. coverage report (after)

  python manage.py enrich_mega --report            # coverage only
  python manage.py enrich_mega --dry-run
  python manage.py enrich_mega
  python manage.py enrich_mega --sets MEG ASC      # subset
  python manage.py enrich_mega --skip-serebii
"""
import re

from django.core.management import call_command
from django.core.management.base import BaseCommand

from products.models import PokemonProduct

MEGA_SETS = ["MEG", "PFL", "MEP", "MEE", "ASC", "POR", "CRI", "BLK", "WHT", "PBL", "30C"]

REPORT_FIELDS = [
    "image_url", "hp", "artist", "stage", "pokedex_number", "weakness_type",
    "retreat_cost", "attack_1_name", "attack_1_cost", "evolves_from",
    "name_japanese", "rules_text",
]


def base_name(name):
    n = re.sub(r'\s*-\s*\d+/\d+\s*$', '', name or '')
    n = re.sub(r'\s*\([^)]*\)\s*$', '', n)
    n = re.sub(r'\s+(ex|EX)$', '', n)
    n = re.sub(r'^Mega\s+', '', n)
    return n.strip().lower()


def clean_display(name):
    n = re.sub(r'\s*-\s*\d+/\d+\s*$', '', name or '')
    return re.sub(r'\s*\([^)]*\)\s*$', '', n).strip()


class Command(BaseCommand):
    help = "Run the full Mega-era enrichment pipeline with before/after coverage."

    def add_arguments(self, parser):
        parser.add_argument("--sets", nargs="+", default=MEGA_SETS)
        parser.add_argument("--report", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-serebii", action="store_true")
        parser.add_argument("--skip-bulbapedia", action="store_true")
        parser.add_argument("--overwrite-fields", default="pokedex_number,ability_type",
                            help="Fields Bulbapedia may overwrite even when filled (default repairs the wrong dex numbers / ability types from the old parser). Use '' to disable.")

    # -- coverage ---------------------------------------------------------
    def coverage(self, sets, title):
        self.stdout.write(f"\n=== Coverage: {title} (% of Pokemon cards with the field) ===")
        head = f"{'set':5} {'cards':>5} {'pkmn':>5} {'types':>6} " + " ".join(f"{f[:9]:>9}" for f in REPORT_FIELDS)
        self.stdout.write(head)
        for code in sets:
            qs = PokemonProduct.objects.filter(card_set__code=code)
            total = qs.count()
            if not total:
                continue
            # "Pokemon-ish": has a supertype of Pokemon, an HP, or a dex number.
            pk_ids = [p.id for p in qs.only("id", "supertype", "hp", "pokedex_number")
                      if (p.supertype or "").lower().startswith("pok") or p.hp or p.pokedex_number]
            pk = qs.filter(id__in=pk_ids)
            n = pk.count() or 1
            types_have = pk.filter(pokemon_types__isnull=False).distinct().count()
            cells = []
            for f in REPORT_FIELDS:
                f_kwargs = {f"{f}__isnull": False}
                have = pk.filter(**f_kwargs).exclude(**{f: ""}).count() if f not in (
                    "hp", "pokedex_number", "retreat_cost") else pk.filter(**f_kwargs).count()
                cells.append(f"{100 * have // n:>8}%")
            self.stdout.write(f"{code:5} {total:>5} {len(pk_ids):>5} {100 * types_have // n:>5}% " + " ".join(cells))
        self.stdout.write("(Trainers/Energy are excluded; unclassified cards = cards - pkmn.)")

    # -- evolves_to -------------------------------------------------------
    def fill_evolves_to(self, sets, dry):
        by_from = {}
        for name, ef in PokemonProduct.objects.exclude(evolves_from="").values_list("name", "evolves_from").distinct():
            by_from.setdefault(ef.strip().lower(), set()).add(clean_display(name))
        to_update = []
        for p in PokemonProduct.objects.filter(card_set__code__in=sets, evolves_to=""):
            targets = by_from.get(base_name(p.name))
            if targets:
                targets = sorted(t for t in targets if t.lower() != clean_display(p.name).lower())
                if targets:
                    p.evolves_to = ", ".join(targets)[:200]
                    to_update.append(p)
        if to_update and not dry:
            PokemonProduct.objects.bulk_update(to_update, ["evolves_to"], batch_size=500)
        self.stdout.write(f"evolves_to filled on {len(to_update)} cards" + (" (DRY RUN)" if dry else ""))

    def handle(self, *args, **o):
        sets = [s.upper() for s in o["sets"]]
        self.coverage(sets, "before")
        if o["report"]:
            return
        if not o["skip_bulbapedia"]:
            self.stdout.write("\n--- Bulbapedia ---")
            call_command("enrich_bulbapedia", *sets, dry_run=o["dry_run"],
                         overwrite_fields=o["overwrite_fields"])
        if not o["skip_serebii"]:
            self.stdout.write("\n--- Serebii ---")
            call_command("enrich_serebii", *sets, dry_run=o["dry_run"])
        self.stdout.write("\n--- evolves_to ---")
        self.fill_evolves_to(sets, o["dry_run"])
        if not o["dry_run"]:
            self.coverage(sets, "after")
