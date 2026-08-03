# PokeBulk SA -- pokedex_number backfill, ROUND 2
#
# Round 1 (backfill_pokedex_numbers.py) only looked at products whose
# supertype was a recognisable Pokemon value (Basic/Stage 1/.../Pokemon) OR
# had a blank supertype but a populated hp field -- that hp check was meant
# to separate real Pokemon from Trainer/Energy cards when supertype itself
# was missing.
#
# verify_search_fixes.py's Pikachu check (2026-08-03) found 115 active
# "Pikachu"-named products still missing pokedex_number after round 1. 108
# of them have BOTH supertype='' AND hp=None -- e.g. plain 'Pikachu',
# 'Pikachu (Secret)', 'Pikachu - 018/091 (Cosmos Holo)'. These are real
# Pokemon cards (secret rares, promos, alt arts) that never got their
# supertype/hp enriched at all -- the hp signal from round 1 wrongly
# excluded them, not because the name-matcher couldn't handle them (it
# trivially can -- "Pikachu" -> #0025), but because they never entered the
# candidate queryset in the first place.
#
# ROUND 2 drops the supertype/hp requirement entirely and considers EVERY
# active product with pokedex_number still null. This is safe because the
# matcher is still exact-match-only: real Trainer/Energy card names
# ("Ultra Ball", "Boss's Orders", "Fire Energy") never coincide with a real
# Pokemon species name, so they will not accidentally match -- confirmed by
# round 1's own no-match list, which correctly rejected "Fire Energy",
# "Alph Lithograph", "Clefairy Doll", "Antique Old/Helix/Dome Fossil" even
# when a stray hp value let them into that run's candidate pool. No new
# risk is introduced by removing the supertype/hp gate.
#
# Same exact-match cleaning logic as backfill_pokedex_numbers.py -- see that
# file's comments for the full history of what's handled (SP-era G/GL/FB/C
# tags, promo codes, regional formes, tag-team splitting, Nidoran M/F, etc).
#
# Usage:
#   python backfill_pokedex_round2.py            # dry run, prints every match
#   python backfill_pokedex_round2.py --apply     # writes to the DB

import django, os, re, sys, json
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
    apply_changes = "--apply" in sys.argv

    if not os.path.exists(REF_PATH):
        print(f"ERROR: {REF_PATH} not found. Run download_pokedex_reference.py first.")
        sys.exit(1)
    with open(REF_PATH, encoding="utf-8") as f:
        ref = json.load(f)
    by_name = {k.lower(): v for k, v in ref["by_name"].items()}
    by_name.setdefault("nidoran m", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran f", by_name.get("nidoran♀"))
    by_name.setdefault("nidoran (m)", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran (f)", by_name.get("nidoran♀"))
    print(f"Loaded {len(by_name)} reference species names.\n")

    # No supertype/hp gate this time -- every still-null active product.
    products = list(PokemonProduct.objects.filter(is_active=True, pokedex_number__isnull=True))
    print(f"Candidate rows to backfill (round 2 -- no supertype/hp filter): {len(products)}\n")

    matched = []
    no_match = []

    for p in products:
        cands = candidates_for(p.name)
        nums = [by_name.get(c.lower()) for c in cands]
        if nums[0] is None:
            no_match.append((p, cands))
            continue
        num1 = nums[0]
        num2 = nums[1] if len(nums) > 1 else None
        if len(nums) > 1 and nums[1] is None:
            no_match.append((p, cands))
            continue
        matched.append((p, num1, num2, cands))

    print(f"MATCHED: {len(matched)}")
    print(f"NO MATCH (expected -- mostly genuine Trainer/Energy/Item cards "
          f"whose names never match a species): {len(no_match)}\n")

    print("--- Sample of matches (first 60) ---")
    for p, n1, n2, cands in matched[:60]:
        tag = f" + #{str(n2).zfill(4)}" if n2 else ""
        print(f"  id={p.id} {p.name!r} supertype={p.supertype!r} -> {cands} -> #{str(n1).zfill(4)}{tag}")

    # No-match list is expected to be large now (all genuine Trainer/Energy/
    # Item rows) -- print a capped sample plus the total so it's reviewable
    # without dumping thousands of "Ultra Ball" / "Fire Energy" lines.
    if no_match:
        print(f"\n--- Sample of no-match rows (first 60 of {len(no_match)} -- spot-check these")
        print(f"    for anything that LOOKS like it should have matched a Pokemon name) ---")
        for p, cands in no_match[:60]:
            print(f"  id={p.id} {p.name!r} supertype={p.supertype!r} -> tried {cands} -> no match")

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
        print(f"{len(no_match)} rows left untouched (see sample above) -- expected to be")
        print(f"genuine Trainer/Energy/Item cards, but worth a final skim.")


if __name__ == "__main__":
    main()
