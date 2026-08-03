# PokeBulk SA -- pokedex_number backfill
#
# Fixes real Pokemon cards confirmed missing a National Dex number
# (diag_pokedex_by_supertype.py + diag_blank_supertype.py showed this
# precisely: Basic/Stage 1/Stage 2/Pokemon/VMAX/VSTAR supertypes, plus
# blank-supertype cards identified via HP).
# Trainer/Energy/Supporter/Stadium cards are correctly left alone -- this
# script only ever touches rows that already look like a real Pokemon card.
#
# Matches against products/data/pokedex_reference.json (built by
# download_pokedex_reference.py -- run that first if this file is missing).
#
# Tag-team cards ("Pikachu & Zekrom-GX") get BOTH pokedex_number and
# pokedex_number_2 set, per Michael's 2026-08-02 request. Everything else
# only ever sets pokedex_number.
#
# v2 (2026-08-03): added after reviewing the v1 dry-run's 546 no-matches --
# extends the cleaner to strip SP-era single/double-letter tags (G/GL/FB/C),
# trailing promo/set codes without a slash (SM07, SVP193, bare card numbers),
# stacked trailing decorations ([Staff] (Prerelease) etc, in any order),
# regional-forme prefixes (Rotom/Ogerpon/Urshifu/Calyrex/Necrozma formes),
# and Nidoran M/F -> the reference's Nidoran(male)/Nidoran(female) symbols.
# Validated against the Bible CSV's 26,017 already-known-correct dex numbers
# before being applied here: 98.7% agreement, 0 new disagreements introduced
# by the v2 changes (only new correct matches).
#
# SAFE BY DESIGN after the TCGdex mixup: never guesses. Every match is an
# EXACT lookup against the real 1025-species reference list after cleaning
# known prefixes/suffixes -- anything that doesn't exactly match goes to the
# "NO MATCH" bucket for manual review, not a fuzzy best-guess.
#
# Usage:
#   python backfill_pokedex_numbers.py            # dry run, prints every match
#   python backfill_pokedex_numbers.py --apply     # writes to the DB

import django, os, re, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct

REF_PATH = os.path.join("products", "data", "pokedex_reference.json")

# Supertype values confirmed (via diag_pokedex_by_supertype.py) to mean
# "this is a Pokemon card" in this catalog -- includes the messy
# subtype-as-supertype values (Basic/Stage 1/Stage 2/VMAX/VSTAR) alongside
# the clean "Pokémon" value, plus the two one-off typos seen in the data
# ("bASIC", "2").
POKEMON_SUPERTYPES = {
    'Basic', 'Stage 1', 'Stage 2', 'Pokémon', 'VMAX', 'VSTAR', 'bASIC', '2',
}

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


def main():
    apply_changes = "--apply" in sys.argv

    if not os.path.exists(REF_PATH):
        print(f"ERROR: {REF_PATH} not found. Run download_pokedex_reference.py first.")
        sys.exit(1)
    with open(REF_PATH, encoding="utf-8") as f:
        ref = json.load(f)
    by_name = {k.lower(): v for k, v in ref["by_name"].items()}
    # Reference only stores the symbol forms -- alias the plain-text forms
    # seen in this catalog ("Nidoran M" / "Nidoran F").
    by_name.setdefault("nidoran m", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran f", by_name.get("nidoran♀"))
    by_name.setdefault("nidoran (m)", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran (f)", by_name.get("nidoran♀"))
    print(f"Loaded {len(by_name)} reference species names.\n")

    qs_supertype = PokemonProduct.objects.filter(
        is_active=True, pokedex_number__isnull=True, supertype__in=POKEMON_SUPERTYPES
    )
    qs_blank_hp = PokemonProduct.objects.filter(
        is_active=True, pokedex_number__isnull=True, supertype='', hp__isnull=False
    )
    products = list(qs_supertype) + list(qs_blank_hp)
    print(f"Candidate rows to backfill: {len(products)}\n")

    matched = []       # (product, num1, num2_or_None, candidates)
    no_match = []       # (product, candidates)

    for p in products:
        cands = candidates_for(p.name)
        nums = [by_name.get(c.lower()) for c in cands]
        if nums[0] is None:
            no_match.append((p, cands))
            continue
        num1 = nums[0]
        num2 = nums[1] if len(nums) > 1 else None
        if len(nums) > 1 and nums[1] is None:
            # Tag-team where only the first half matched -- still record the
            # partial match but flag it so it gets a human look, not silently
            # applied with a missing second number.
            no_match.append((p, cands))
            continue
        matched.append((p, num1, num2, cands))

    print(f"MATCHED: {len(matched)}")
    print(f"NO MATCH (needs manual review): {len(no_match)}\n")

    print("--- Sample of matches (first 40) ---")
    for p, n1, n2, cands in matched[:40]:
        tag = f" + #{str(n2).zfill(4)}" if n2 else ""
        print(f"  {p.name!r} -> {cands} -> #{str(n1).zfill(4)}{tag}")

    if no_match:
        print(f"\n--- ALL no-match rows (review these manually) ---")
        for p, cands in no_match:
            print(f"  id={p.id} {p.name!r} -> tried {cands} -> no exact reference match")

    if not apply_changes:
        print(f"\nDRY RUN -- nothing written. Review the matches above (especially check for")
        print(f"any that look wrong), then rerun with --apply to write {len(matched)} rows.")
        return

    to_update = []
    for p, n1, n2, cands in matched:
        p.pokedex_number = n1
        if n2:
            p.pokedex_number_2 = n2
        to_update.append(p)

    PokemonProduct.objects.bulk_update(to_update, ['pokedex_number', 'pokedex_number_2'], batch_size=500)
    print(f"\nApplied: {len(to_update)} products updated.")
    if no_match:
        print(f"{len(no_match)} rows still need manual review (see list above) -- not touched.")


if __name__ == "__main__":
    main()
