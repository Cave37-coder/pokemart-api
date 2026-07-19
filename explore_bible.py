"""
Quick pandas exploration of tcgcsv_bible.csv.

Usage: python explore_bible.py
Requires: pip install pandas
"""
import pandas as pd

df = pd.read_csv("tcgcsv_bible.csv")

print(f"Total rows: {len(df):,}")
print(f"Columns: {list(df.columns)}\n")

# Rows per game
print("=== Rows per game ===")
print(df.groupby("game_name").size().sort_values(ascending=False))

# Rows per product type
print("\n=== Rows per product type ===")
print(df["product_type"].value_counts())

# Example: just Magic singles
magic_singles = df[(df["game_code"] == "magic") & (df["product_type"] == "single")]
print(f"\nMagic singles: {len(magic_singles):,}")

# Example: search by name (case-insensitive)
charizard = df[df["name"].str.contains("Charizard", case=False, na=False)]
print(f"\nRows matching 'Charizard': {len(charizard)}")
print(charizard[["game_name", "set_name", "name", "market_price"]].head(10))

# Example: highest-priced items overall
print("\n=== Top 10 highest market_price ===")
print(
    df.sort_values("market_price", ascending=False)
    [["game_name", "set_name", "name", "market_price"]]
    .head(10)
)

# Save a filtered subset back out, e.g. just One Piece
# df[df["game_code"] == "one-piece"].to_csv("one_piece_only.csv", index=False)
