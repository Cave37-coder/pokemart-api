"""
Full enrichment of POR Perfect Order CSV from Django DB.

Enriches with: artist, Japanese name, HP, attacks, ability,
weakness, resistance, retreat, flavour text, Pokedex number,
corrected release date, rebuilds full description.

Run from project root:
    cd C:\\Users\\texca\\pokemart-api
    python enrich_por_csv.py

Input:  por_input.csv  (rename your uploaded POR file to this)
Output: por_enriched.csv
"""

import os, re, sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import pandas as pd
from products.models import PokemonProduct

RELEASE_DATE = "2026/03/27"
SET_CODE     = "POR"
INPUT_FILE   = "por_input.csv"
OUTPUT_FILE  = "por_enriched.csv"

# ── Load CSV ──────────────────────────────────────────────────────────────────
if not os.path.exists(INPUT_FILE):
    print(f"X {INPUT_FILE} not found in project root.")
    print("  Rename your POR CSV to por_input.csv and place it here.")
    sys.exit(1)

df = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False)
print(f"Loaded {len(df)} rows from {INPUT_FILE}")

# ── Build card data map from DB ───────────────────────────────────────────────
print("Fetching card data from DB...")

products = PokemonProduct.objects.filter(
    card_set__code=SET_CODE
).select_related("card_set")

card_map = {}
for p in products:
    num = str(p.card_number)
    if num not in card_map or (
        not card_map[num].get("attack_1_name") and p.attack_1_name
    ):
        card_map[num] = {
            "artist":          p.artist or "",
            "name_japanese":   p.name_japanese or "",
            "hp":              p.hp or "",
            "supertype":       p.supertype or "",
            "card_subtypes":   p.card_subtypes or "",
            "ability_name":    p.ability_name or "",
            "ability_type":    p.ability_type or "",
            "ability_text":    p.ability_text or "",
            "attack_1_name":   p.attack_1_name or "",
            "attack_1_damage": p.attack_1_damage or "",
            "attack_1_text":   p.attack_1_text or "",
            "attack_2_name":   p.attack_2_name or "",
            "attack_2_damage": p.attack_2_damage or "",
            "attack_2_text":   p.attack_2_text or "",
            "weakness_type":   p.weakness_type or "",
            "weakness_value":  p.weakness_value or "",
            "resistance_type": p.resistance_type or "",
            "retreat_cost":    str(p.retreat_cost) if p.retreat_cost else "",
            "flavour_text":    p.flavour_text or "",
            "pokedex_number":  str(p.pokedex_number) if p.pokedex_number else "",
        }

print(f"Found data for {len(card_map)} unique cards")


def get_card_num(sku):
    m = re.match(r'me3-(\d+)-', sku)
    return str(int(m.group(1))) if m else None


def build_description(row, data, release_date):
    rarity_raw     = row["option:Rarity"]
    rarity_display = rarity_raw.replace("_", " ").title()
    card_num_raw   = get_card_num(row["sku"])

    m = re.search(r"Number in Set: ([\d/]+)", row["description"])
    num_in_set = m.group(1) if m else f"{int(card_num_raw):03d}/088"

    parts = []
    parts.append(f"Series: Mega Evolution")
    parts.append(f"Set: Perfect Order")
    parts.append(f"Rarity: {rarity_display}")
    parts.append(f"Release Date: {release_date}")
    parts.append(f"Artist: {data['artist'] or 'Unknown'}")
    parts.append(f"Number in Set: {num_in_set}")

    if data["name_japanese"]:
        parts.append(f"Japanese Name: {data['name_japanese']}")
    if data["hp"]:
        parts.append(f"HP: {data['hp']}")
    if data["card_subtypes"]:
        parts.append(f"Stage: {data['card_subtypes']}")
    if data["weakness_type"]:
        w = data["weakness_type"]
        if data["weakness_value"]:
            w += f" {data['weakness_value']}"
        parts.append(f"Weakness: {w}")
    if data["resistance_type"]:
        parts.append(f"Resistance: {data['resistance_type']}")
    if data["retreat_cost"]:
        parts.append(f"Retreat Cost: {data['retreat_cost']}")
    if data["ability_name"]:
        parts.append(f"Ability: {data['ability_name']}")
        if data["ability_text"]:
            parts.append(f"Ability Text: {data['ability_text']}")
    if data["attack_1_name"]:
        atk = data["attack_1_name"]
        if data["attack_1_damage"]:
            atk += f" ({data['attack_1_damage']})"
        parts.append(f"Attack 1: {atk}")
        if data["attack_1_text"]:
            parts.append(f"Attack 1 Text: {data['attack_1_text']}")
    if data["attack_2_name"]:
        atk = data["attack_2_name"]
        if data["attack_2_damage"]:
            atk += f" ({data['attack_2_damage']})"
        parts.append(f"Attack 2: {atk}")
        if data["attack_2_text"]:
            parts.append(f"Attack 2 Text: {data['attack_2_text']}")
    if data["flavour_text"]:
        parts.append(f"Flavour Text: {data['flavour_text']}")
    if data["pokedex_number"]:
        parts.append(f"Pokedex No.: {data['pokedex_number']}")

    # Build HTML
    inner = "<br />\n".join(parts)
    return f"<p>{inner}</p>"


# ── Enrich ────────────────────────────────────────────────────────────────────
print("Enriching rows...")
updated   = 0
not_found = []

for idx, row in df.iterrows():
    card_num = get_card_num(row["sku"])
    if not card_num:
        continue

    data = card_map.get(card_num)
    if not data:
        not_found.append(card_num)
        continue

    df.at[idx, "option:Artist"] = data["artist"] or "Unknown"
    df.at[idx, "description"]   = build_description(row, data, RELEASE_DATE)
    updated += 1

df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print()
print("-" * 50)
print(f"  Enriched : {updated} rows")
if not_found:
    unique = sorted(set(not_found), key=lambda x: int(x))
    print(f"  Missing  : cards {', '.join(unique[:20])}")
    if len(unique) > 20:
        print(f"             ... +{len(unique)-20} more")
print(f"  Output   : {OUTPUT_FILE}")
print("-" * 50)

# Show a sample
sample = df[df['sku'] == 'me3-4-norm']
if len(sample):
    print()
    print("Sample description (card 4):")
    print(sample['description'].iloc[0])
