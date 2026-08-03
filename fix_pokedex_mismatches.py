# PokeBulk SA -- fixes the 310 pre-existing pokedex_number mistags found by
# audit_pokedex_mismatches.py, split into two very different buckets:
#
# BUCKET 1 -- "missing pokedex_number_2 only" (SAFE, additive):
#   Tag-team / LEGEND split cards (Team Up, Unbroken Bonds, Unified Minds,
#   Cosmic Eclipse GX pairs; Undaunted/Unleashed/Triumphant LEGEND halves)
#   already have the CORRECT pokedex_number -- they're just missing
#   pokedex_number_2 for the second Pokemon, because they already had a
#   number set before today's backfill scripts ran (which only ever fill
#   NULL values). This bucket only ADDS pokedex_number_2, never changes an
#   existing value. Zero risk of breaking something that was already right.
#
# BUCKET 2 -- "pokedex_number itself is wrong" (NEEDS REVIEW, overwrites):
#   Three different-looking root causes bundled together here:
#     (a) Systematic off-by-one in White Flare/Black Bolt/Chaos Rising/
#         Perfect Order/Mega Evolution -- every single sampled row in these
#         sets is EXACTLY "stored = correct - 1", suggesting one shared
#         import bug for that batch, not random typos.
#     (b) Base Set Shadowless -- ~40 products with scattered/shuffled wrong
#         values (not off-by-one) -- this is the same set Michael spotted
#         Dratini/Farfetch'd/Growlithe in on /pokedex/25.
#     (c) A handful of isolated one-offs elsewhere (Ponyta/Celebrations --
#         already known from the CLB image-fix session; Oranguru, Rockruff,
#         Sinistcha, Probopass, Ambipom, Honchkrow, Gliscor, Archaludon,
#         Mamoswine).
#   This bucket OVERWRITES an existing value, so it prints full detail and
#   requires --apply-bucket2 specifically (separate from --apply-bucket1)
#   so nothing gets overwritten by accident.
#
# Usage:
#   python fix_pokedex_mismatches.py                     # dry run, both buckets
#   python fix_pokedex_mismatches.py --apply-bucket1      # writes ONLY the safe additions
#   python fix_pokedex_mismatches.py --apply-bucket1 --apply-bucket2   # writes both

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
    apply_b1 = "--apply-bucket1" in sys.argv
    apply_b2 = "--apply-bucket2" in sys.argv

    with open(REF_PATH, encoding="utf-8") as f:
        ref = json.load(f)
    by_name = {k.lower(): v for k, v in ref["by_name"].items()}
    by_name.setdefault("nidoran m", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran f", by_name.get("nidoran♀"))
    by_name.setdefault("nidoran (m)", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran (f)", by_name.get("nidoran♀"))
    print(f"Loaded {len(by_name)} reference species names.\n")

    products = PokemonProduct.objects.filter(is_active=True, pokedex_number__isnull=False).select_related('card_set')

    bucket1 = []  # (product, num2_to_add) -- pokedex_number already correct
    bucket2 = []  # (product, num1, num2_or_None) -- pokedex_number itself wrong

    for p in products.iterator(chunk_size=1000):
        cands = candidates_for(p.name)
        nums = [by_name.get(c.lower()) for c in cands]
        if nums[0] is None or (len(nums) > 1 and nums[1] is None):
            continue
        matcher_num1 = nums[0]
        matcher_num2 = nums[1] if len(nums) > 1 else None
        stored = {p.pokedex_number, p.pokedex_number_2} - {None}
        matched_set = {matcher_num1}
        if matcher_num2:
            matched_set.add(matcher_num2)
        if stored == matched_set:
            continue  # already correct

        if p.pokedex_number == matcher_num1 and matcher_num2 and p.pokedex_number_2 is None:
            bucket1.append((p, matcher_num2))
        elif p.pokedex_number == matcher_num2 and matcher_num2 and p.pokedex_number_2 is None:
            # tag-team where the SECOND matcher slot matches the existing
            # primary -- still just an additive fix, add num1 as the second slot
            bucket1.append((p, matcher_num1))
        else:
            bucket2.append((p, matcher_num1, matcher_num2))

    print(f"BUCKET 1 -- safe, additive (pokedex_number already correct, just add pokedex_number_2): {len(bucket1)}")
    for p, num2 in bucket1[:15]:
        print(f"  id={p.id} {p.name!r} set={p.card_set.name if p.card_set else '?'!r} "
              f"pokedex_number={p.pokedex_number} (kept) + pokedex_number_2={num2} (new)")
    if len(bucket1) > 15:
        print(f"  ... and {len(bucket1) - 15} more")

    print(f"\nBUCKET 2 -- pokedex_number ITSELF is wrong, needs overwrite (review before applying): {len(bucket2)}")
    for p, n1, n2 in bucket2:
        stored_str = f"{p.pokedex_number}" + (f"/{p.pokedex_number_2}" if p.pokedex_number_2 else "")
        should_str = f"{n1}" + (f"/{n2}" if n2 else "")
        print(f"  id={p.id} {p.name!r:45s} set={(p.card_set.name if p.card_set else '?')!r:30s} "
              f"stored={stored_str} -> {should_str}")

    if apply_b1:
        to_update = []
        for p, num2 in bucket1:
            p.pokedex_number_2 = num2
            to_update.append(p)
        PokemonProduct.objects.bulk_update(to_update, ['pokedex_number_2'], batch_size=500)
        print(f"\nBucket 1 applied: {len(to_update)} rows got pokedex_number_2 added.")
    else:
        print(f"\nBucket 1: dry run only -- rerun with --apply-bucket1 to write these {len(bucket1)} rows.")

    if apply_b2:
        to_update = []
        for p, n1, n2 in bucket2:
            p.pokedex_number = n1
            p.pokedex_number_2 = n2
            to_update.append(p)
        PokemonProduct.objects.bulk_update(to_update, ['pokedex_number', 'pokedex_number_2'], batch_size=500)
        print(f"Bucket 2 applied: {len(to_update)} rows had pokedex_number corrected.")
    else:
        print(f"Bucket 2: dry run only -- rerun with --apply-bucket2 to write these {len(bucket2)} rows"
              f" (do this only after reviewing the full list above).")


if __name__ == "__main__":
    main()
