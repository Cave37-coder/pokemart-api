"""
Counts exact live product totals for every category on TCGCSV (the same
public mirror of TCGplayer data that PokemonProduct.tcgcsv_product_id
already ties into) -- not just the three we picked by hand last time.

Usage: python tcgcsv_count_all.py
Requires: pip install requests

Respects TCGCSV's usage guidelines (custom User-Agent, small delay
between requests) -- see https://tcgcsv.com/docs

Heads up: this will take a while. Some categories (Magic, YuGiOh, Pokemon
Japan) have hundreds of sets, each needing its own request. Progress
prints as it goes so it doesn't look stuck.
"""
import time
import requests

USER_AGENT = "PokeBulkSA-SizeCheck/1.0"
HEADERS = {"User-Agent": USER_AGENT}

# Real per-product cost, calculated from PokeBulk's own live Postgres stats:
# 39.2 MB data + 19.9 MB indexes across 38,554 rows = ~1.53 KB/row.
KB_PER_PRODUCT = 1.53

# Correction factor: TCGCSV counts one row per printing. PokeBulk's own
# database stores ~1.19x that (multiple rows per condition, per the
# CONDITION_CHOICES field) -- calculated from the Pokemon comparison:
# 38,554 real DB rows / 32,474 TCGCSV products = 1.19
DB_ROW_MULTIPLIER = 1.19


def get_categories():
    resp = requests.get("https://tcgcsv.com/tcgplayer/categories", headers=HEADERS).json()
    return resp["results"]


def count_products_for_category(category_id):
    groups_url = f"https://tcgcsv.com/tcgplayer/{category_id}/groups"
    groups_resp = requests.get(groups_url, headers=HEADERS).json()
    groups = groups_resp.get("results", [])

    total_products = 0
    for group in groups:
        products_url = f"https://tcgcsv.com/tcgplayer/{category_id}/{group['groupId']}/products"
        resp = requests.get(products_url, headers=HEADERS).json()
        total_products += resp.get("totalItems", 0)
        time.sleep(0.1)  # be a good neighbor, per TCGCSV's docs

    return len(groups), total_products


if __name__ == "__main__":
    categories = get_categories()
    print(f"Found {len(categories)} categories. Starting count...\n")

    results = []
    for i, cat in enumerate(categories, 1):
        name = cat["displayName"] or cat["name"]
        cat_id = cat["categoryId"]
        print(f"[{i}/{len(categories)}] {name}...", end=" ", flush=True)
        try:
            num_sets, num_products = count_products_for_category(cat_id)
            results.append((name, num_sets, num_products))
            print(f"{num_sets} sets, {num_products} products")
        except Exception as e:
            print(f"skipped ({e})")

    results.sort(key=lambda r: r[2], reverse=True)

    print("\n" + "=" * 60)
    print(f"{'Category':<40} {'Sets':>6} {'Products':>10}")
    print("-" * 60)
    total_products_all = 0
    for name, num_sets, num_products in results:
        print(f"{name:<40} {num_sets:>6} {num_products:>10}")
        total_products_all += num_products

    est_db_rows = total_products_all * DB_ROW_MULTIPLIER
    est_size_mb = (est_db_rows * KB_PER_PRODUCT) / 1024

    print("-" * 60)
    print(f"{'TOTAL':<40} {'':>6} {total_products_all:>10}")
    print("=" * 60)
    print(f"\nIf every category above were imported the same way Pokemon is:")
    print(f"  Estimated database rows: {est_db_rows:,.0f}")
    print(f"  Estimated size: {est_size_mb:,.1f} MB")
