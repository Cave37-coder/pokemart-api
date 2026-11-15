# PokeBulk SA -- adds pokedex numbers to the master Bible CSV.
#
# Same exact-match-only logic as backfill_pokedex_numbers.py (the DB script),
# applied here to pokebulk_bible_v7_r2.csv so the source-of-truth catalog
# carries correct, 4-digit-padded National Dex numbers going forward.
#
# Adds two new columns to every row:
#   pokedex_1  -- primary Pokemon's dex number, zero-padded to 4 digits
#   pokedex_2  -- second Pokemon's number for tag-team cards ("X & Y"), else blank
#
# Fill priority per row:
#   1. If final_pokedex is already populated, use it (trusts existing data).
#   2. Else, if the exact-match cleaner finds the species in the reference
#      list, use that.
#   3. Else leave blank -- goes in the no-match report for manual review.
#
# Rows whose final_pokedex disagrees with the matcher are NOT silently
# overwritten -- they're written to a separate disagreement report so a
# human decides which is right (see backfill_bible_report.txt).
#
# Only rows that look like real Pokemon cards get touched: card_type is a
# Pokemon energy-type (Water/Grass/Psychic/etc), OR card_type is blank but
# hp is set (same signal used on the live DB diagnostic).

import csv, json, re, os

IN_PATH = "/sessions/wonderful-beautiful-lovelace/mnt/uploads/9e6ec667-fa13-4c6f-88a1-e4c51e501ad5-1785733350874_pokebulk_bible_v7_r2.csv"
REF_PATH = "/sessions/wonderful-beautiful-lovelace/mnt/pokemart-api/products/data/pokedex_reference.json"
OUT_CSV = "/sessions/wonderful-beautiful-lovelace/mnt/outputs/pokebulk_bible_v7_r2_with_pokedex.csv"
OUT_REPORT = "/sessions/wonderful-beautiful-lovelace/mnt/outputs/backfill_bible_report.txt"

POKEMON_CARD_TYPES = {
    "Water", "Grass", "Psychic", "Colorless", "Fighting", "Fire",
    "Lightning", "Darkness", "Metal", "Dragon", "Fairy",
}

PREFIX_STRIP = [
    r"^mega\s+", r"^m\s+",
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


def pad(n):
    return str(int(n)).zfill(4)


def main():
    with open(REF_PATH, encoding="utf-8") as f:
        ref = json.load(f)
    by_name = {k.lower(): v for k, v in ref["by_name"].items()}
    by_name.setdefault("nidoran m", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran f", by_name.get("nidoran♀"))
    by_name.setdefault("nidoran (m)", by_name.get("nidoran♂"))
    by_name.setdefault("nidoran (f)", by_name.get("nidoran♀"))
    print(f"Loaded {len(by_name)} reference species.")

    with open(IN_PATH, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) + ["pokedex_1", "pokedex_2"]
        rows = list(reader)
    print(f"Loaded {len(rows)} Bible rows.")

    filled_from_existing = 0
    filled_from_matcher = 0
    left_blank = 0
    skipped_non_pokemon = 0
    disagreements = []
    no_match = []

    for row in rows:
        card_type = (row.get("card_type") or "").strip()
        hp = (row.get("hp") or "").strip()
        is_pokemon_row = card_type in POKEMON_CARD_TYPES or (card_type == "" and hp != "")

        row["pokedex_1"] = ""
        row["pokedex_2"] = ""

        if not is_pokemon_row:
            skipped_non_pokemon += 1
            continue

        name = (row.get("clean_name") or row.get("name") or "").strip()
        final_pokedex = (row.get("final_pokedex") or "").strip()

        cands = candidates_for(name)
        nums = [by_name.get(c.lower()) for c in cands]
        matcher_num1 = nums[0] if nums else None
        matcher_num2 = nums[1] if len(nums) > 1 else None
        matcher_val = None
        if matcher_num1 is not None and not (len(nums) > 1 and matcher_num2 is None):
            matcher_val = (matcher_num1, matcher_num2)

        if final_pokedex:
            parts = [p for p in re.split(r"[|,]", final_pokedex) if p.strip().isdigit()]
            if parts:
                existing_val = (int(parts[0]), int(parts[1]) if len(parts) > 1 else None)
                row["pokedex_1"] = pad(existing_val[0])
                if existing_val[1]:
                    row["pokedex_2"] = pad(existing_val[1])
                filled_from_existing += 1

                if matcher_val and matcher_val[0] != existing_val[0]:
                    disagreements.append((name, cands, matcher_val, existing_val, row.get("set_name", "")))
                continue

        if matcher_val:
            row["pokedex_1"] = pad(matcher_val[0])
            if matcher_val[1]:
                row["pokedex_2"] = pad(matcher_val[1])
            filled_from_matcher += 1
        else:
            left_blank += 1
            no_match.append((row.get("product_id", ""), name, row.get("set_name", ""), cands))

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write(f"Bible pokedex backfill report\n")
        f.write(f"Total rows: {len(rows)}\n")
        f.write(f"Skipped (not a Pokemon row -- Trainer/Energy/etc): {skipped_non_pokemon}\n")
        f.write(f"Filled from existing final_pokedex: {filled_from_existing}\n")
        f.write(f"Filled newly from name-matcher: {filled_from_matcher}\n")
        f.write(f"Left blank (no exact match): {left_blank}\n")
        f.write(f"Disagreements (existing final_pokedex vs matcher): {len(disagreements)}\n\n")

        f.write("=== DISAGREEMENTS (existing value kept, matcher NOT applied -- review manually) ===\n")
        for name, cands, mv, ev, set_name in disagreements:
            f.write(f"  {name!r:25s} set={set_name!r:30s} cands={cands} matcher={mv[0]} vs existing={ev[0]}\n")

        f.write("\n=== NO MATCH (left blank, needs manual lookup) ===\n")
        for pid, name, set_name, cands in no_match:
            f.write(f"  product_id={pid} {name!r:35s} set={set_name!r:30s} tried={cands}\n")

    print(f"\nSkipped non-Pokemon rows: {skipped_non_pokemon}")
    print(f"Filled from existing final_pokedex: {filled_from_existing}")
    print(f"Filled newly from matcher: {filled_from_matcher}")
    print(f"Left blank (no match): {left_blank}")
    print(f"Disagreements flagged: {len(disagreements)}")
    print(f"\nWrote: {OUT_CSV}")
    print(f"Wrote: {OUT_REPORT}")


if __name__ == "__main__":
    main()
