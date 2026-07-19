"""
Counts exact live product totals per TCG category from TCGCSV (the same
public mirror of TCGplayer data that PokemonProduct.tcgcsv_product_id
already ties into).

Usage: python tcgcsv_count.py
Requires: pip install requests

Respects TCGCSV's usage guidelines (custom User-Agent, small delay
between requests) -- see https://tcgcsv.com/docs
"""
import time
import requests

USER_AGENT = "PokeBulkSA-SizeCheck/1.0"
HEADERS = {"User-Agent": USER_AGENT}

# Confirmed exact category IDs as of July 2026
CATEGORIES = {
    "Magic: The Gathering": 1,
    "Pokemon": 3,
    "One Piece Card Game": 68,
}


def count_products_for_category(category_id):
    groups_url = f"https://tcgcsv.com/tcgplayer/{category_id}/groups"
    groups = requests.get(groups_url, headers=HEADERS).json()["results"]

    total_products = 0
    for i, group in enumerate(groups, 1):
        products_url = f"https://tcgcsv.com/tcgplayer/{category_id}/{group['groupId']}/products"
        resp = requests.get(products_url, headers=HEADERS).json()
        total_products += resp.get("totalItems", 0)
        time.sleep(0.1)  # be a good neighbor, per TCGCSV's docs

    return len(groups), total_products


if __name__ == "__main__":
    print(f"{'Game':<25} {'Sets':>6} {'Products':>10}")
    print("-" * 43)
    for name, cat_id in CATEGORIES.items():
        num_sets, num_products = count_products_for_category(cat_id)
        print(f"{name:<25} {num_sets:>6} {num_products:>10}")
