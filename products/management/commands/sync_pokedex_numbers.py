# products/management/commands/sync_pokedex_numbers.py
#
# Michael, 2026-09-29: "we have to create an update script to run against
# all checklists, pokedex script, to update with any new cards added to any
# of them, the pokedex is so out of date with the site!"
#
# The "checklists" half of that already exists -- generate_checklist_data
# regenerates checklistData.ts from the DB, and Michael already runs it
# after every new-card sync (most recently for the 30th Celebration
# additions). This command is the missing "pokedex" half.
#
# ROOT CAUSE of the staleness: a PokemonProduct only shows up on ANY
# /pokedex/[id] or /collections/[id] page once it has a `pokedex_number`
# set (see getAllCardsForPokedex's `?pokedex=<id>` filter in both those
# pages) -- but sync_tcgcsv.py, which is what actually creates new product
# rows, never sets pokedex_number itself (TCGCSV's own data has no such
# field). So every new card synced in -- a whole new set, or a handful of
# previously-missing cards like the 30th Celebration Kommo-o/SIR/RGB Mew
# fix -- lands with pokedex_number = NULL and is invisible to both Pokedex
# features until something backfills it. Nothing was re-running that
# backfill after the initial one-time pass back in August, so the Pokedex
# has been quietly falling behind the real catalog ever since.
#
# This is a straight port of backfill_pokedex_round2.py's matching logic
# (itself a superset of the original backfill_pokedex_numbers.py -- round 2
# dropped the supertype/hp gate that round 1 used and was safely validated
# to introduce zero new mismatches) into a permanent, reusable management
# command instead of a one-off root script -- the "go forward" tool for
# this. It is ALREADY incremental/idempotent by construction: it only ever
# looks at rows where pokedex_number IS NULL, so running it again after
# adding more cards only touches whatever's new. Re-run this any time after
# a sync_tcgcsv run (or any other way new products get added) to keep the
# Pokedex current.
#
# SAFE BY DESIGN: every match is an EXACT lookup against the real 1025-
# species National Dex reference after cleaning known prefixes/suffixes
# (Mega/regional formes, -ex/-GX/V/VMAX/VSTAR, tag-team "X & Y" splitting,
# trailing set-number/bracket/paren/promo-code decorations, Nidoran M/F).
# Anything that doesn't exactly match goes to the "no match" list for a
# human to review -- never a fuzzy best-guess. This only ever fills in a
# currently-NULL value; it never overwrites an existing pokedex_number (see
# the separate, already-run audit_pokedex_mismatches.py / fix_pokedex_
# mismatches.py for the different, human-reviewed problem of a handful of
# pre-existing WRONG values from an old import bug).
#
# Depends on products/data/pokedex_reference.json (built once by
# download_pokedex_reference.py from pokeapi.co's National Dex list -- this
# essentially never needs rebuilding, since the reference covers the full,
# now-static 1-1025 range). If that file is missing, this command says so
# and stops rather than guessing.
#
# Usage:
#   python manage.py sync_pokedex_numbers            # dry run, prints every match
#   python manage.py sync_pokedex_numbers --apply     # writes to the DB

import json
import os
import re

from django.core.management.base import BaseCommand, CommandError

from products.models import PokemonProduct

REF_PATH = os.path.join("products", "data", "pokedex_reference.json")

PREFIX_STRIP = [
    r"^mega\s+", r"^m\s+",  # "Mega Charizard EX", old-style "M Charizard EX"
    r"^shining\s+", r"^dark\s+", r"^light\s+", r"^crystal\s+", r"^radiant\s+",
    r"^shiny\s+", r"^galarian\s+", r"^alolan\s+", r"^hisuian\s+", r"^paldean\s+",
    r"^detective\s+", r"^origin\s+forme\s+", r"^poncho-wearing\s+",
    r"^heat\s+", r"^wash\s+", r"^frost\s+", r"^fan\s+", r"^mow\s+", r"^cut\s+",  # Rotom formes
    r"^teal\s+mask\s+", r"^wellspring\s+mask\s+", r"^hearthflame\s+mask\s+", r"^cornerstone\s+mask\s+",  # Ogerpon
    r"^single\s+strike\s+", r"^rapid\s+strike\s+",  # Urshifu
    r"^shadow\s+rider\s+", r"^ice\s+rider\s+",  # Calyrex
    r"^dawn\s+wings\s+", r"^dusk\s+mane\s+", r"^ultra\s+",  # Necrozma
    r"^armored\s+",  # Armored Mewtwo (Detective Pikachu promo)
    r"^bloodmoon\s+",  # Bloodmoon Ursaluna
    r"^white\s+", r"^black\s+",  # White/Black Kyurem
]

SUFFIX_STRIP = [
    r"\s+ex$", r"-ex$", r"\s+gx$", r"-gx$", r"\s+v-union$", r"\s+vunion$",
    r"\s+vmax$", r"\s+vstar$", r"\s+v$", r"\s+prime$", r"\s+lv\.?\s*x$",
    r"\s+legend$", r"\s+star$", r"\s+x$", r"\s+y$", r"\s*\*$", r"\s+δ$",
    r"\s+gl$", r"\s+fb$", r"\s+g$", r"\s+c$",  # SP-era single/double-letter tags
]

POSSESSIVE = re.compile(r"^.+?['’]s\s+", re.IGNORECASE)  # handles both ' and the curly '

# Trailing "decorations" get stripped in a loop since they stack in any
# order -- e.g. "Amoonguss - SM202 (Prerelease) [Staff]" needs the bracket,
# then the paren, then the "- SM202" code removed, one at a time.
TRAIL_BRACKET = re.compile(r"\s*\[[^\]]*\]\s*$")
TRAIL_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
TRAIL_SETNUM = re.compile(r"\s*-\s*\d+/\d+\s*$")          # "- 025/167"
TRAIL_SLASHCODE = re.compile(r"\s*-\s*\d+/[A-Za-z0-9-]+\s*$")  # "- 38/SM-P"
TRAIL_BARECODE = re.compile(r"\s*-\s*[A-Za-z]{0,4}\d+[A-Za-z]{0,2}\s*$")  # "- SM104a", "- 074"


def strip_trailing_decorations(name):
    prev = None
    while prev != name:
        prev = name
        name = TRAIL_BRACKET.sub("", name)
        name = TRAIL_PAREN.sub("", name)
        name = TRAIL_SETNUM.sub("", name)
        name = TRAIL_SLASHCODE.sub("", name)
        name = TRAIL_BARECODE.sub("", name)
    return name.strip()


def clean_candidate(raw):
    name = raw.strip()
    name = strip_trailing_decorations(name)
    name = POSSESSIVE.sub("", name)  # "Ash's Pikachu" -> "Pikachu"
    for pat in PREFIX_STRIP:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    for pat in SUFFIX_STRIP:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    return strip_trailing_decorations(name.strip()).strip()


def candidates_for(raw_name):
    """Returns a list of 1 or 2 cleaned candidate names -- 2 for tag-team
    ("X & Y") cards, 1 otherwise."""
    base = strip_trailing_decorations(raw_name.strip())
    if " & " in base:
        parts = base.split(" & ", 1)
        return [clean_candidate(parts[0]), clean_candidate(parts[1])]
    return [clean_candidate(base)]


class Command(BaseCommand):
    help = (
        "Backfill pokedex_number (+ pokedex_number_2 for tag-team cards) for every "
        "active product that doesn't have one yet -- run any time after new cards are "
        "added (e.g. after sync_tcgcsv) to keep /pokedex and /collections current. "
        "Only ever fills a NULL value; never overwrites an existing one."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes to the DB. Without this, dry-run only.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        if not os.path.exists(REF_PATH):
            raise CommandError(
                f"{REF_PATH} not found. Run `python download_pokedex_reference.py` "
                f"from the repo root first (one-time, only needed if that file is missing)."
            )
        with open(REF_PATH, encoding="utf-8") as f:
            ref = json.load(f)
        by_name = {k.lower(): v for k, v in ref["by_name"].items()}
        # Reference only stores the symbol forms -- alias the plain-text forms
        # seen in this catalog ("Nidoran M" / "Nidoran F").
        by_name.setdefault("nidoran m", by_name.get("nidoran♂"))
        by_name.setdefault("nidoran f", by_name.get("nidoran♀"))
        by_name.setdefault("nidoran (m)", by_name.get("nidoran♂"))
        by_name.setdefault("nidoran (f)", by_name.get("nidoran♀"))
        self.stdout.write(f"Loaded {len(by_name)} reference species names.\n")

        # No supertype/hp gate -- every still-null active product is a candidate.
        # See the module docstring for why round 1's narrower gate (now retired)
        # missed real Pokemon cards whose supertype/hp were never enriched at all.
        products = list(PokemonProduct.objects.filter(is_active=True, pokedex_number__isnull=True))
        self.stdout.write(f"Candidate rows (pokedex_number still NULL): {len(products)}\n")

        matched = []   # (product, num1, num2_or_None, candidates)
        no_match = []  # (product, candidates)

        for p in products:
            cands = candidates_for(p.name)
            nums = [by_name.get(c.lower()) for c in cands]
            if nums[0] is None:
                no_match.append((p, cands))
                continue
            num1 = nums[0]
            num2 = nums[1] if len(nums) > 1 else None
            if len(nums) > 1 and nums[1] is None:
                # Tag-team where only the first half matched -- flag for a
                # human look rather than silently applying a missing 2nd number.
                no_match.append((p, cands))
                continue
            matched.append((p, num1, num2, cands))

        self.stdout.write(self.style.SUCCESS(f"MATCHED: {len(matched)}"))
        self.stdout.write(f"NO MATCH (expected -- mostly genuine Trainer/Energy/Item cards "
                           f"whose names never match a species): {len(no_match)}\n")

        self.stdout.write("--- Sample of matches (first 60) ---")
        for p, n1, n2, cands in matched[:60]:
            tag = f" + #{str(n2).zfill(4)}" if n2 else ""
            self.stdout.write(f"  id={p.id} {p.name!r} -> {cands} -> #{str(n1).zfill(4)}{tag}")

        if no_match:
            self.stdout.write(f"\n--- Sample of no-match rows (first 60 of {len(no_match)} -- spot-check")
            self.stdout.write(f"    for anything that LOOKS like it should have matched a Pokemon name) ---")
            for p, cands in no_match[:60]:
                self.stdout.write(f"  id={p.id} {p.name!r} -> tried {cands} -> no match")

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN -- nothing written. Review the matches above (especially check for "
                f"any that look wrong), then rerun with --apply to write {len(matched)} rows."
            ))
            return

        to_update = []
        for p, n1, n2, cands in matched:
            p.pokedex_number = n1
            if n2:
                p.pokedex_number_2 = n2
            to_update.append(p)

        PokemonProduct.objects.bulk_update(to_update, ["pokedex_number", "pokedex_number_2"], batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"\nApplied: {len(to_update)} products updated."))
        if no_match:
            self.stdout.write(f"{len(no_match)} rows left untouched (see sample above) -- expected to be "
                               f"genuine Trainer/Energy/Item cards, but worth a final skim.")
