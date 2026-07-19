"""
Shows 50 rows of the genuinely ambiguous ones: name suggests a sealed
product, classified as 'single', but with NEITHER a card_number NOR a
rarity (so there's no obvious reason the heuristic called it 'single').

Usage: python show_ambiguous_sealed.py
Requires: pip install pandas
"""
import pandas as pd

pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", None)

df = pd.read_csv("tcgcsv_bible.csv", low_memory=False)

SEALED_KEYWORDS = [
    "Booster Box", "Booster Pack", "Booster Bundle",
    "Elite Trainer Box", "Starter Deck", "Structure Deck",
    "Theme Deck", "Precon", "Preconstructed",
    "Bundle", "Case", "Display", "Blister",
    "Collection Box", "Gift Box", "Fat Pack",
    "Trainer Box", "Tin", "Box Set",
]

name_matches_keyword = df["name"].str.contains(
    "|".join(SEALED_KEYWORDS), case=False, na=False
)

ambiguous = df[
    name_matches_keyword
    & (df["product_type"] == "single")
    & (df["card_number"].isna())
    & (df["rarity"].isna())
]

print(f"Total ambiguous rows: {len(ambiguous)}\n")
print(
    ambiguous[["game_name", "set_name", "name", "market_price"]]
    .head(50)
    .to_string()
)
