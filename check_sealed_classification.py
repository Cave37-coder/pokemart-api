"""
Investigates the low sealed-product count by searching for common sealed-
product keywords among rows classified as 'single' or 'accessory'. If a
lot of "Booster Box"/"Elite Trainer Box"/etc. names show up outside the
'sealed' bucket, that confirms the classification heuristic is
misreading them -- rather than sealed genuinely being underrepresented
in TCGCSV's catalog.

Usage: python check_sealed_classification.py
Requires: pip install pandas
"""
import pandas as pd

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

print(f"Total rows: {len(df):,}")
print(f"Rows whose NAME suggests sealed product: {name_matches_keyword.sum():,}\n")

print("=== Where those name-matched rows actually landed ===")
print(df[name_matches_keyword]["product_type"].value_counts())

print("\n=== Sample of name-matched rows currently classified as 'single' ===")
misclassified = df[name_matches_keyword & (df["product_type"] == "single")]
print(f"Count: {len(misclassified):,}\n")
print(misclassified[["game_name", "set_name", "name", "card_number", "rarity"]].head(20).to_string())

print("\n=== Sample of name-matched rows currently classified as 'accessory' ===")
misclassified_acc = df[name_matches_keyword & (df["product_type"] == "accessory")]
print(f"Count: {len(misclassified_acc):,}\n")
print(misclassified_acc[["game_name", "set_name", "name", "card_number", "rarity"]].head(10).to_string())

# Breakdown: of the misclassified-as-single rows, how many actually have
# a non-empty card_number/rarity (meaning the heuristic had a real reason
# to call them 'single', vs how many have blank number/rarity and were
# misclassified for some other reason)
print("\n=== Of the misclassified 'single' rows, do they have real card_number/rarity? ===")
print("Have card_number:", misclassified["card_number"].notna().sum())
print("Have rarity:", misclassified["rarity"].notna().sum())
print("Have NEITHER (genuinely no reason to be 'single'):",
      ((misclassified["card_number"].isna()) & (misclassified["rarity"].isna())).sum())
