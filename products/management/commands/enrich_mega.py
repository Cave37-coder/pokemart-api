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
from django.db.models import Count

from products.models import PokemonProduct, CardSet
from products.management.commands.enrich_only import SET_ID_MAP
from products.management.commands.enrich_bulbapedia import BULBA_SETS
from products.management.commands.enrich_serebii import SEREBII_SLUGS

# Era codes (Era.code), newest first -- used by --era-from.
ERA_CODES_NEW_TO_OLD = ["MEG", "SV", "SWSH", "SM", "XY", "BW", "HGSS", "DP", "EX", "WotCO", "WotCL", "WotCN", "WotC"]

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
        parser.add_argument("--era-from", default="",
                            help="Run every set from this era up to the newest, e.g. BW. Uses pokemontcg.io "
                                 "(fast, full cards) for the mapped sets, plus Bulbapedia/Serebii where configured.")
        parser.add_argument("--skip-ptcgio", action="store_true")
        parser.add_argument("--report", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-serebii", action="store_true")
        parser.add_argument("--skip-bulbapedia", action="store_true")
        parser.add_argument("--twins-only", action="store_true",
                            help="Skip the web sources; just run the twin-copy + evolves_to passes (fast).")
        parser.add_argument("--overwrite-fields", default="pokedex_number,ability_type",
                            help="Fields Bulbapedia may overwrite even when filled (default repairs the wrong dex numbers / ability types from the old parser). Use '' to disable.")

    # -- coverage ---------------------------------------------------------
    def coverage(self, sets, title):
        self.stdout.write(f"\n=== Coverage: {title} (% of Pokemon cards with the field) ===")
        head = f"{'set':5} {'cards':>5} {'pkmn':>5} {'types':>6} " + " ".join(f"{f[:9]:>9}" for f in REPORT_FIELDS)
        self.stdout.write(head)
        # Many sets (era mode) -> one row per ERA instead of one per set.
        if len(sets) > 20:
            groups = {}
            for code, era in CardSet.objects.filter(code__in=sets).values_list("code", "era__code"):
                groups.setdefault(era or "?", []).append(code)
            rows = [(era, {"card_set__code__in": codes}) for era, codes in groups.items()]
        else:
            rows = [(code, {"card_set__code": code}) for code in sets]
        for code, flt in rows:
            qs = PokemonProduct.objects.filter(**flt)
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

    # -- twins ------------------------------------------------------------
    def fill_from_twins(self, sets, dry):
        """Alt prints / reprints / promo prints (MEG 133-188, MEP, ASC reprints)
        have no Bulbapedia page of their own. Copy the print-independent
        fields from an already-enriched card with the same name + HP + first
        attack, ANYWHERE in the DB, when all matching cards agree. Never
        copies artist, image, price or anything print-specific."""
        def norm(name):
            n = re.sub(r'\[[^\]]*\]', '', name or '')
            n = re.sub(r'\([^)]*\)', '', n)
            n = re.sub(r'-?\s*\d+(?:/\d+)?', '', n)
            n = re.sub(r'\s+', ' ', n).strip(' -').lower()
            return n

        COPY = ["stage", "evolves_from", "evolves_to", "name_japanese",
                "ability_2_name", "ability_2_type", "ability_2_text",
                "attack_3_name", "attack_3_damage", "attack_3_text", "attack_3_cost",
                "rules_text", "ancient_trait", "card_level", "card_subtypes"]
        donors = {}
        for p in PokemonProduct.objects.exclude(stage="").filter(hp__isnull=False):
            key = (norm(p.name), p.hp, (p.attack_1_name or "").lower())
            donors.setdefault(key, []).append(p)

        to_update = []
        for p in PokemonProduct.objects.filter(card_set__code__in=sets, stage="", hp__isnull=False):
            cands = donors.get((norm(p.name), p.hp, (p.attack_1_name or "").lower()))
            if not cands or len({c.stage for c in cands}) != 1:
                continue
            d = cands[0]
            changed = False
            for f in COPY:
                if not getattr(p, f) and getattr(d, f):
                    setattr(p, f, getattr(d, f))
                    changed = True
            if changed:
                to_update.append(p)
        if to_update and not dry:
            PokemonProduct.objects.bulk_update(to_update, COPY, batch_size=500)
        self.stdout.write(f"twin-copy filled {len(to_update)} cards" + (" (DRY RUN)" if dry else ""))

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
        era_mode = bool(o["era_from"])
        if era_mode:
            ef = o["era_from"]
            if ef not in ERA_CODES_NEW_TO_OLD:
                raise SystemExit(f"--era-from must be one of {ERA_CODES_NEW_TO_OLD}")
            eras = ERA_CODES_NEW_TO_OLD[:ERA_CODES_NEW_TO_OLD.index(ef) + 1]
            sets = list(CardSet.objects.filter(era__code__in=eras).values_list("code", flat=True))
            self.stdout.write(f"Era mode: {', '.join(eras)} -> {len(sets)} sets")
            # Sets no source can reach (not mapped to pokemontcg.io, Bulbapedia
            # or Serebii) -- these keep their holes until a mapping is added.
            unmapped = [
                (c, n, cnt) for c, n, cnt in (
                    CardSet.objects.filter(code__in=sets).annotate(cnt=Count("products"))
                    .values_list("code", "name", "cnt"))
                if c not in SET_ID_MAP and c not in BULBA_SETS and c not in SEREBII_SLUGS and cnt
            ]
            self.stdout.write(f"\nSets with NO source mapping ({len(unmapped)}) -- will not be enriched:")
            for c, n, cnt in sorted(unmapped, key=lambda x: -x[2]):
                self.stdout.write(f"  {c:8} {cnt:>5} cards  {n}")
        self.coverage(sets, "before")
        if o["report"]:
            return
        if o["twins_only"]:
            o["skip_bulbapedia"] = o["skip_serebii"] = o["skip_ptcgio"] = True
        # 1) pokemontcg.io -- every mapped set (BW .. SV). Fast, full card data.
        if era_mode and not o["skip_ptcgio"]:
            self.stdout.write("\n--- pokemontcg.io ---")
            for code in sets:
                if code in SET_ID_MAP:
                    call_command("enrich_only", code, dry_run=o["dry_run"])
        bulba_sets = [c for c in sets if c in BULBA_SETS]
        if not o["skip_bulbapedia"] and bulba_sets:
            self.stdout.write("\n--- Bulbapedia ---")
            call_command("enrich_bulbapedia", *bulba_sets, dry_run=o["dry_run"],
                         overwrite_fields=o["overwrite_fields"])
        serebii_sets = [c for c in sets if c in SEREBII_SLUGS]
        if not o["skip_serebii"] and serebii_sets:
            self.stdout.write("\n--- Serebii ---")
            call_command("enrich_serebii", *serebii_sets, dry_run=o["dry_run"])
        self.stdout.write("\n--- twin copy (alt/reprint/promo prints) ---")
        self.fill_from_twins(sets, o["dry_run"])
        self.stdout.write("\n--- evolves_to ---")
        self.fill_evolves_to(sets, o["dry_run"])
        if not o["dry_run"]:
            self.coverage(sets, "after")
