# PokeBulk SA -- National Dex reference list builder
#
# Michael, 2026-08-02: "create a script to download all Pokedex numbers,
# but they must be padded to 4 eg 0025, see there currently 1025!"
#
# Builds the canonical 1-1025 National Dex reference (padded 4-digit number
# -> display name, plus the reverse lookup) that the pokedex_number backfill
# script will match card names against. Run on YOUR machine, not in a
# sandbox -- needs real internet access to pokeapi.co, which the dev
# sandbox this session ran in can't reach (network-restricted).
#
# Name formatting is ported line-for-line from the frontend's
# src/lib/pokedex.ts (NAME_OVERRIDES + formatPokemonName), so the backend
# reference list matches exactly what the /pokedex pages already display --
# no risk of the two disagreeing on "Ho-Oh" vs "Ho-oh" etc.
#
# Output: products/data/pokedex_reference.json
#   {
#     "by_number": {"0001": "Bulbasaur", ..., "1025": "..."},
#     "by_name":   {"bulbasaur": 1, ...}          <- lowercase name -> int id
#   }
#
# Usage:
#   python download_pokedex_reference.py

import json
import os
import re
import time
import requests

OUT_PATH = os.path.join("products", "data", "pokedex_reference.json")
NATIONAL_DEX_TOTAL = 1025

# Ported verbatim from src/lib/pokedex.ts NAME_OVERRIDES.
NAME_OVERRIDES = {
    "nidoran-f": "Nidoran♀", "nidoran-m": "Nidoran♂",
    "mr-mime": "Mr. Mime", "mr-rime": "Mr. Rime", "mime-jr": "Mime Jr.",
    "farfetchd": "Farfetch'd", "sirfetchd": "Sirfetch'd",
    "type-null": "Type: Null", "ho-oh": "Ho-Oh", "porygon-z": "Porygon-Z",
    "flabebe": "Flabébé",
    "jangmo-o": "Jangmo-o", "hakamo-o": "Hakamo-o", "kommo-o": "Kommo-o",
    "tapu-koko": "Tapu Koko", "tapu-lele": "Tapu Lele", "tapu-bulu": "Tapu Bulu", "tapu-fini": "Tapu Fini",
    "ting-lu": "Ting-Lu", "chien-pao": "Chien-Pao", "wo-chien": "Wo-Chien", "chi-yu": "Chi-Yu",
    "great-tusk": "Great Tusk", "scream-tail": "Scream Tail", "brute-bonnet": "Brute Bonnet",
    "flutter-mane": "Flutter Mane", "slither-wing": "Slither Wing", "sandy-shocks": "Sandy Shocks",
    "iron-treads": "Iron Treads", "iron-bundle": "Iron Bundle", "iron-hands": "Iron Hands",
    "iron-jugulis": "Iron Jugulis", "iron-moth": "Iron Moth", "iron-thorns": "Iron Thorns",
    "roaring-moon": "Roaring Moon", "iron-valiant": "Iron Valiant", "walking-wake": "Walking Wake",
    "iron-leaves": "Iron Leaves", "gouging-fire": "Gouging Fire", "raging-bolt": "Raging Bolt",
    "iron-boulder": "Iron Boulder", "iron-crown": "Iron Crown",
}


def format_pokemon_name(slug):
    if slug in NAME_OVERRIDES:
        return NAME_OVERRIDES[slug]
    return " ".join(part.capitalize() for part in slug.split("-"))


def main():
    print(f"Fetching National Dex species list (1-{NATIONAL_DEX_TOTAL}) from pokeapi.co...")
    resp = requests.get(
        "https://pokeapi.co/api/v2/pokemon-species",
        params={"limit": NATIONAL_DEX_TOTAL, "offset": 0},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    print(f"  Got {len(results)} entries")

    by_number = {}
    by_name = {}
    for r in results:
        m = re.search(r"/pokemon-species/(\d+)/", r["url"])
        if not m:
            continue
        dex_id = int(m.group(1))
        if dex_id < 1 or dex_id > NATIONAL_DEX_TOTAL:
            continue
        display_name = format_pokemon_name(r["name"])
        padded = str(dex_id).zfill(4)
        by_number[padded] = display_name
        by_name[display_name.lower()] = dex_id

    missing = [n for n in range(1, NATIONAL_DEX_TOTAL + 1) if str(n).zfill(4) not in by_number]
    if missing:
        print(f"  WARNING: {len(missing)} dex numbers missing from the response: {missing[:20]}{'...' if len(missing) > 20 else ''}")
    else:
        print(f"  Complete -- all {NATIONAL_DEX_TOTAL} entries present, padded 0001-{NATIONAL_DEX_TOTAL}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"by_number": by_number, "by_name": by_name}, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"\nWrote {OUT_PATH}")
    print(f"  by_number entries: {len(by_number)}")
    print(f"  by_name entries:   {len(by_name)}")
    print(f"\nSample: 0001={by_number.get('0001')!r}  0025={by_number.get('0025')!r}  1025={by_number.get('1025')!r}")


if __name__ == "__main__":
    main()
