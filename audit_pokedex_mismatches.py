# PokeBulk SA -- audits EXISTING pokedex_number/pokedex_number_2 values
# catalog-wide for mistags, rather than just filling in blanks.
#
# Michael spotted Dratini, Farfetch'd and Growlithe (all WotC Black Star
# Promos, 026-028/102) showing up on /pokedex/25 (Pikachu) -- their
# pokedex_number is already 0025 in the DB, and that predates today's
# backfill entirely (backfill_pokedex_numbers.py / round2 only ever fill
# NULL values, never touch a row that already has a number). So this is
# pre-existing bad data, not something introduced today -- the question is
# how widespread it is across the rest of the 36k-product catalog.
#
# For every active product that already HAS a pokedex_number, this re-runs
# the same exact-match name-cleaner used in the backfill scripts. If the
# cleaned name maps to a DIFFERENT species than what's stored, it's flagged.
# Rows where the cleaner can't confidently resolve a name (ambiguous/complex)
# are left alone -- this only flags cases where we have a confident, exact,
# alternative answer, same safety principle as every other script today.
#
# Read-only -- makes no DB changes.
#
# Usage:
#   python audit_pokedex_mismatches.py

import django, os, re, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct

REF_PATH = os.path.join("products", "data", "pokedex_reference.json")

PREFIX_STRIP = [
    r"^mega\s+", r"^m\s+",
    r"^shining\s+", r"^dark\s+", r"^light\s+", r"^crystal\s+", r"^radiant\s+",
    r"^shiny\s+", r"^galarian\s+", r"^alolan\s+", r"^hisuian\s+", r"^paldean\s+",
    r"^detective\s+", r"^origin\s+forme\s+", r"^poncho-wearing\s+",
    r"^heat\s+", r"^wash\s+", r"^frost\s+", r"^fan\s+", r"^mow\s+", r"^cut\s+",
    r"^teal\s+mask\s+", r"^wellspring\s+mask\s+", r"^hearthflame\s+mask\s+", r"^cornerstone\s+mask\s+",
    r"^single\s+strike\s+", r"^rapid\s+strike\s+",
    r"^shadow\s+rider\s+", r"^ice\s+rider\s+",
    r"^dawn\s+wings\s+", r"^dusk\s+mane\s+", r"^ultra\s+",
    r"^armored\s+",
    r"^bloodmoon\s+",
    r"^white\s+", r"^black\s+",
]

SUFFIX_STRIP = [
    r"\s+ex$", r"-ex$", r"\s+gx$", r"-gx$", r"\s+v-union$", r"\s+vunion$",
    r"\s+vmax$", r"\s+vstar$", r"\s+v$", r"\s+prime$", r"\s+lv\.?\s*x$",
    r"\s+legend$", r"\s+star$", r"\s+x$", r"\s+y$", r"\s*\*$", r"\s+δ$",
    r"\s+gl$", r"\s+fb$", r"\s+g$", r"\s+c$",
]

POSSESSIVE = re.compile(r"^.+?['’]s\s+", re.IGNORECASE)
TRAIL_BRACKET = re.compile(r"\s*\[[^\]]*\]\s*$")
TRAIL_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
TRAIL_SETNUM = re.compile(r"\s*-\s*\d+/\d+\s*$")
TRAIL_SLASHCODE = re.compile(r"\s*-\s*\d+/[A-Za-z0-9-]+\s*$")
TRAIL_BARECODE = re.compile(r"\s*-\s*[A-Za-z]{0,4}\d+[A-Za-z]{0,2}\s*$")


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
    name = POSSESSIVE.sub("", name)
    for pat in PREFIX_STRIP:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    for pat in SUFFIX_STRIP:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    return strip_trailing_decorations(name.strip()).strip()


def candidates_for(raw_name):
    base = strip_trailing_decorations(raw_name.strip())
    if " & " in base:
        parts = base.split(" & ", 1)
        return [clean_candidate(parts[0]), clean_candidate(parts[1])]
    return [clean_candidate(base)]


def main():
    with open(REF_PATH, encoding="utf-8") as f:
        ref = json.load(f)
    by_name = {k.lower(): v for k, v in ref["by_name"].items()}
    by_name.setdefault("nidoran m", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran f", by_name.get("nidoran♀"))
    by_name.setdefault("nidoran (m)", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran (f)", by_name.get("nidoran♀"))
    print(f"Loaded {len(by_name)} reference species names.\n")

    products = PokemonProduct.objects.filter(
        is_active=True, pokedex_number__isnull=False
    ).select_related('card_set')
    total = products.count()
    print(f"Active products with a pokedex_number already set: {total}\n")

    mismatches = []
    checked = 0
    unresolved = 0

    for p in products.iterator(chunk_size=1000):
        cands = candidates_for(p.name)
        nums = [by_name.get(c.lower()) for c in cands]
        if nums[0] is None or (len(nums) > 1 and nums[1] is None):
            unresolved += 1
            continue
        checked += 1
        matcher_num1 = nums[0]
        matcher_num2 = nums[1] if len(nums) > 1 else None
        stored = {p.pokedex_number, p.pokedex_number_2} - {None}
        matched_set = {matcher_num1}
        if matcher_num2:
            matched_set.add(matcher_num2)
        if stored != matched_set:
            mismatches.append((p, matcher_num1, matcher_num2))

    print(f"Rows the matcher could confidently resolve: {checked}")
    print(f"Rows the matcher couldn't confidently resolve (skipped, not flagged): {unresolved}")
    print(f"\nCONFIRMED MISTAGS (matcher disagrees with stored value): {len(mismatches)}\n")

    print("--- All mismatches (id, name, set, stored -> should-be) ---")
    for p, n1, n2 in mismatches:
        stored_str = f"{p.pokedex_number}" + (f"/{p.pokedex_number_2}" if p.pokedex_number_2 else "")
        should_str = f"{n1}" + (f"/{n2}" if n2 else "")
        set_name = p.card_set.name if p.card_set else "?"
        print(f"  id={p.id} {p.name!r:45s} set={set_name!r:30s} stored={stored_str} -> should be {should_str}")

    print("\nNothing written -- this is a read-only audit. Review the list above,")
    print("then let me know if you want a script to fix these (it would need")
    print("your explicit go-ahead per row-count, same as every other backfill today).")


if __name__ == "__main__":
    main()
