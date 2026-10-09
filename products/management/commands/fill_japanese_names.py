"""
fill_japanese_names.py - PokeBulk SA

Fills blank `name_japanese` for Pokemon cards from PokeAPI species data, by
National Pokedex number (Michael, 2026-10-08: "Japanese names for BW..SV").
pokemontcg.io has no Japanese names, and Bulbapedia/TCGdex are too slow to
crawl card-by-card for ~25k cards -- one PokeAPI call per SPECIES (~1000) is
enough because the printed Japanese card name is just the species' katakana
name plus an optional prefix/suffix.

CONSERVATIVE by design -- a card only gets a name when its English name is
exactly  [prefix] <species English name> [suffix]  where:
  prefix in: Mega / Alolan / Galarian / Hisuian / Paldean / Radiant
  suffix in: ex / EX / GX / V / VMAX / VSTAR
and the species English name matches the card's Pokemon. Anything else
(Team Rocket's X, Dark X, trainer-owned Pokemon, tag teams, Mega X/Y, Prism
Star, odd promo names...) is SKIPPED, never guessed. Fill-only: never
overwrites an existing name_japanese.

  python manage.py fill_japanese_names --dry-run
  python manage.py fill_japanese_names
  python manage.py fill_japanese_names --sets MEG SV   # era codes or set codes
"""
import re
import time

import requests
from django.core.management.base import BaseCommand

from products.models import PokemonProduct, CardSet

API = "https://pokeapi.co/api/v2/pokemon-species/{}"
HEADERS = {"User-Agent": "PokeBulkSA-CardEnrichment/1.0 (https://pokebulk.co.za; enquiries@pokebulk.co.za)"}

PREFIX_JA = {
    "mega": "メガ", "alolan": "アローラ", "galarian": "ガラル",
    "hisuian": "ヒスイ", "paldean": "パルデア", "radiant": "かがやく",
}
# Alolan/Galarian/... are printed on Japanese cards as  アローラ<species>
# (no separator) -- same pattern as メガ + species.
SUFFIXES = ("VSTAR", "VMAX", "GX", "EX", "ex", "V")


def clean(name):
    n = re.sub(r"\s*-\s*\d+(?:/\d+)?", "", name or "")       # " - 133/132"
    n = re.sub(r"\[[^\]]*\]", "", n)                           # "[Staff]"
    n = re.sub(r"\([^)]*\)", "", n)                            # "(Poke Ball)"
    return re.sub(r"\s+", " ", n).strip()


def alnum(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# Bracketed words that change the PRINTED Japanese name (special card types),
# as opposed to print variants like "(Poke Ball)" / "(Cosmos Holo)" which keep
# the same name. A card with one of these is skipped, never guessed.
SPECIAL_PAREN = re.compile(
    r"\((?:[^)]*\b)?(prime|legend|lv\.?\s*x|level|break|star|delta|tera|prism|radiant|mega|tag|"
    r"shining|dark|light|ancient|future|team|g\s*max|dynamax|gigantamax|alolan|galarian|hisuian|paldean)\b[^)]*\)",
    re.I)


def split_name(name):
    """-> (prefix_key or '', core, suffix or '') or None if unsupported shape."""
    if SPECIAL_PAREN.search(name or ""):
        return None
    n = clean(name)
    prefix = ""
    first, _, rest = n.partition(" ")
    if first.lower() in PREFIX_JA and rest:
        prefix, n = first.lower(), rest
    suffix = ""
    for s in SUFFIXES:
        if n.endswith(" " + s):
            suffix, n = s, n[: -len(s) - 1]
            break
    return prefix, n.strip(), suffix


class Command(BaseCommand):
    help = "Fill blank name_japanese from PokeAPI by Pokedex number (conservative, fill-only)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--sets", nargs="*", default=[],
                            help="Set codes and/or era codes (e.g. MEG SV SWSH). Default: all sets.")
        parser.add_argument("--delay", type=float, default=0.12)
        parser.add_argument("--report-skipped", action="store_true",
                            help="List why/which cards were skipped (no changes if combined with --dry-run).")

    def handle(self, *args, **o):
        qs = PokemonProduct.objects.filter(name_japanese="", pokedex_number__isnull=False,
                                           pokedex_number_2__isnull=True)
        if o["sets"]:
            codes = [s.upper() if s.upper() in ("MEG", "SV", "SWSH", "SM", "XY", "BW", "HGSS", "DP", "EX") else s
                     for s in o["sets"]]
            set_codes = list(CardSet.objects.filter(code__in=o["sets"]).values_list("code", flat=True))
            era_codes = [c for c in codes if c in ("MEG", "SV", "SWSH", "SM", "XY", "BW", "HGSS", "DP", "EX")]
            if era_codes:
                set_codes += list(CardSet.objects.filter(era__code__in=era_codes).values_list("code", flat=True))
            qs = qs.filter(card_set__code__in=set_codes)
        cards = list(qs.select_related("card_set__era").only(
            "id", "name", "pokedex_number", "card_set__code", "card_set__era__code"))
        dex_numbers = sorted({c.pokedex_number for c in cards})
        self.stdout.write(f"{len(cards)} cards without a Japanese name, {len(dex_numbers)} species to look up")

        species = {}   # dex -> (english_name, ja_name)
        for i, dex in enumerate(dex_numbers, 1):
            for attempt in range(3):
                try:
                    r = requests.get(API.format(dex), headers=HEADERS, timeout=20)
                except requests.RequestException:
                    r = None
                if r is not None and r.status_code == 200:
                    names = {n["language"]["name"]: n["name"] for n in r.json().get("names", [])}
                    ja = names.get("ja-hrkt") or names.get("ja")
                    species[dex] = (names.get("en", ""), ja)
                    break
                if r is not None and r.status_code == 404:
                    break
                time.sleep(2 * (attempt + 1))
            time.sleep(o["delay"])
            if i % 100 == 0:
                self.stdout.write(f"  looked up {i}/{len(dex_numbers)} species")

        to_update, skipped = [], 0
        skipped_names = []   # (reason, card name) for --report-skipped
        for c in cards:
            info = species.get(c.pokedex_number)
            if not info or not info[1]:
                skipped += 1
                skipped_names.append(("no species/ja name", c.name))
                continue
            en, ja = info
            parts = split_name(c.name)
            if parts is None:
                skipped += 1
                skipped_names.append(("special card type", c.name))
                continue
            prefix, core, suffix = parts
            if alnum(core) != alnum(en):
                skipped += 1          # not a plain "<species>" -- don't guess
                skipped_names.append(("name != species", c.name))
                continue
            if suffix in ("ex", "EX"):
                # Modern (SV/Mega) cards print lowercase "ex" (our DB often
                # stores "EX"); XY/BW-era cards print uppercase "EX".
                era = c.card_set.era.code if c.card_set and c.card_set.era else ""
                suffix = "ex" if (era in ("MEG", "SV") or prefix == "mega") else "EX"
            c.name_japanese = PREFIX_JA.get(prefix, "") + ja + suffix
            to_update.append(c)

        self.stdout.write(f"will fill {len(to_update)} cards; skipped {skipped} (unsupported name shape or no match)")
        for c in to_update[:8]:
            self.stdout.write(f"  e.g. {c.name!r} -> {c.name_japanese}")
        if o["report_skipped"]:
            from collections import Counter
            self.stdout.write("\nSkipped, by reason:")
            for reason, n in Counter(r for r, _ in skipped_names).most_common():
                self.stdout.write(f"  {n:>5}  {reason}")
            # group by the card name with set numbering stripped, most common first
            shapes = Counter(clean(n) for _, n in skipped_names)
            self.stdout.write("\nMost common skipped names (top 60):")
            for name, n in shapes.most_common(60):
                self.stdout.write(f"  {n:>4}  {name}")
            self.stdout.write("\nSample of the rest (every 40th):")
            for _, n in skipped_names[::40][:40]:
                self.stdout.write(f"       {n}")
        if o["dry_run"]:
            self.stdout.write("DRY RUN - nothing saved")
            return
        PokemonProduct.objects.bulk_update(to_update, ["name_japanese"], batch_size=500)
        self.stdout.write(self.style.SUCCESS("Done."))
