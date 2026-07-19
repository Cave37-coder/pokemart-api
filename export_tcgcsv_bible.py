"""
Exports a full CSV snapshot of every product across the confirmed game
shortlist + accessory categories, straight from TCGCSV. Meant as a
reference "bible" -- a point-in-time dataset to build/test against later,
independent of whether TCGCSV is reachable or has changed by then.

Usage: python export_tcgcsv_bible.py
Requires: pip install requests

Output: tcgcsv_bible.csv in the current directory. Writes incrementally
(one row at a time) rather than holding everything in memory, so it's
safe even if interrupted partway -- you'll just have a partial file
instead of losing everything.

Respects TCGCSV's usage guidelines (custom User-Agent, small delay
between requests) -- see https://tcgcsv.com/docs

Heads up: this is a big pull. Magic alone is 450 sets. Expect this to
run for a while -- progress prints per set so it's clear it's working,
not stuck.
"""
import csv
import time

import requests

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
USER_AGENT = "PoBuSA-BibleExport/1.0"
HEADERS = {"User-Agent": USER_AGENT}
OUTPUT_FILE = "tcgcsv_bible.csv"

# Confirmed shortlist -- (game_code, display_name, tcgcsv_category_id)
GAMES = [
    ("magic", "Magic: The Gathering", 1),
    ("yugioh", "Yu-Gi-Oh!", 2),
    ("one-piece", "One Piece Card Game", 68),
    ("dragon-ball-super", "Dragon Ball Super: Masters", 27),
    ("dragon-ball-fusion", "Dragon Ball Super: Fusion World", 80),
    ("digimon", "Digimon Card Game", 63),
    ("star-wars-unlimited", "Star Wars: Unlimited", 79),
    ("gundam", "Gundam Card Game", 86),
    ("riftbound", "Riftbound: League of Legends Trading Card Game", 89),
    ("lorcana", "Disney Lorcana", 71),
]

# Accessory categories -- game-agnostic, product_type forced to 'accessory'
ACCESSORY_CATEGORIES = [
    ("supplies", "Supplies", 14),
    ("card-sleeves", "Card Sleeves", 31),
    ("deck-boxes", "Deck Boxes", 32),
    ("card-storage-tins", "Card Storage Tins", 33),
    ("life-counters", "Life Counters", 34),
    ("playmats", "Playmats", 35),
    ("protective-pages", "Protective Pages", 49),
    ("storage-albums", "Storage Albums", 50),
    ("collectible-storage", "Collectible Storage", 51),
    ("supply-bundles", "Supply Bundles", 52),
    ("tcgplayer-supplies", "TCGplayer Supplies", 82),
]

CSV_COLUMNS = [
    "game_code", "game_name", "product_type",
    "set_name", "set_abbreviation",
    "card_number", "variant", "rarity",
    "name", "market_price", "image_url",
    "tcgcsv_category_id", "tcgcsv_group_id", "tcgcsv_product_id",
]


def fetch_prices(category_id, group_id):
    resp = requests.get(f"{TCGCSV_BASE}/{category_id}/{group_id}/prices", headers=HEADERS).json()
    by_product = {}
    for pr in resp.get("results", []):
        pid = pr["productId"]
        if pid not in by_product and pr.get("marketPrice") is not None:
            by_product[pid] = pr["marketPrice"]
    return by_product


def export_category(writer, category_id, game_code, game_name, forced_type):
    groups_resp = requests.get(f"{TCGCSV_BASE}/{category_id}/groups", headers=HEADERS).json()
    groups = groups_resp.get("results", [])
    row_count = 0

    for i, group in enumerate(groups, 1):
        price_by_product = fetch_prices(category_id, group["groupId"])

        products_resp = requests.get(
            f"{TCGCSV_BASE}/{category_id}/{group['groupId']}/products", headers=HEADERS
        ).json()

        for p in products_resp.get("results", []):
            extended = {e["name"]: e["value"] for e in p.get("extendedData", [])}
            card_number = extended.get("Number", "") or extended.get("CardNumber", "")
            rarity = extended.get("Rarity", "")

            if forced_type:
                product_type = forced_type
            else:
                product_type = "single" if ("Number" in extended or "Rarity" in extended) else "sealed"

            writer.writerow({
                "game_code": game_code,
                "game_name": game_name,
                "product_type": product_type,
                "set_name": group["name"],
                "set_abbreviation": group.get("abbreviation", ""),
                "card_number": card_number,
                "variant": extended.get("Printing", "") or extended.get("SubType", ""),
                "rarity": rarity,
                "name": p["name"],
                "market_price": price_by_product.get(p["productId"], ""),
                "image_url": p.get("imageUrl", ""),
                "tcgcsv_category_id": category_id,
                "tcgcsv_group_id": group["groupId"],
                "tcgcsv_product_id": p["productId"],
            })
            row_count += 1

        time.sleep(0.1)  # be a good neighbor, per TCGCSV's docs
        print(f"    [{i}/{len(groups)}] {group['name']} ({row_count} rows so far)")

    return row_count


if __name__ == "__main__":
    total_rows = 0

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for game_code, game_name, category_id in GAMES:
            print(f"\n=== {game_name} (category {category_id}) ===")
            total_rows += export_category(writer, category_id, game_code, game_name, forced_type=None)

        for cat_code, cat_name, category_id in ACCESSORY_CATEGORIES:
            print(f"\n=== {cat_name} (accessory, category {category_id}) ===")
            total_rows += export_category(writer, category_id, None, cat_name, forced_type="accessory")

    print(f"\nDone. {total_rows} total rows written to {OUTPUT_FILE}")
