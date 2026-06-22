"""
Pulls every Pokemon-related product under TCGCSV's "Card Sleeves" category
(categoryId 31 -- confirmed via https://tcgcsv.com/tcgplayer/categories,
separate from Pokemon's own categoryId 3 since sleeves are a shared
category across every TCG TCGplayer carries) and writes a CSV using the
same column conventions as pokebulk_bible_v6.csv, minus everything that's
card-specific and meaningless for a sleeve (attacks, HP, stage, weakness,
resistance, retreat cost, pokedex number, regulation mark, all the
Bulbapedia/pokemontcg.io enrichment columns -- there's no equivalent
enrichment source for sleeves).

Pricing formula matches the documented pipeline:
    pokebulk_zar = round_up_to_nearest_R0.50(max(market_usd * zar_rate * 1.10, R1.50))
with the same 3-source ZAR rate fallback chain (Frankfurter ECB ->
ExchangeRate-API -> fawazahmed0 CDN).

Usage:
    python pull_pokemon_sleeves.py                # Pokemon-filtered only (default)
    python pull_pokemon_sleeves.py --all           # every sleeve in the category, any game
"""
import csv
import math
import sys
import time
from datetime import datetime, timezone

import requests

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
CARD_SLEEVES_CATEGORY_ID = 31
REQUEST_DELAY_SECONDS = 0.3

POKEMON_KEYWORDS = ["pokemon", "pokémon", "pikachu", "eevee", "charizard", "gengar"]


TCGCSV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def get_json(url):
    resp = requests.get(url, headers=TCGCSV_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def is_pokemon_related(group_name, product_name):
    haystack = f"{group_name} {product_name}".lower()
    return any(kw in haystack for kw in POKEMON_KEYWORDS)


def get_usd_zar_rate():
    """3-source fallback chain, matching the documented pricing pipeline."""
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=ZAR", timeout=10)
        r.raise_for_status()
        rate = r.json()["rates"]["ZAR"]
        print(f"USD/ZAR rate from Frankfurter (ECB): {rate}")
        return rate
    except Exception as e:
        print(f"Frankfurter failed: {e}")

    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        rate = r.json()["rates"]["ZAR"]
        print(f"USD/ZAR rate from ExchangeRate-API: {rate}")
        return rate
    except Exception as e:
        print(f"ExchangeRate-API failed: {e}")

    try:
        r = requests.get(
            "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
            timeout=10,
        )
        r.raise_for_status()
        rate = r.json()["usd"]["zar"]
        print(f"USD/ZAR rate from fawazahmed0 CDN: {rate}")
        return rate
    except Exception as e:
        print(f"fawazahmed0 CDN failed: {e}")

    print("WARNING: all 3 rate sources failed. Falling back to a hardcoded estimate -- VERIFY before trusting pokebulk_zar values.")
    return 18.0


def compute_pokebulk_zar(market_usd, zar_rate):
    if market_usd is None or market_usd == "":
        return ""
    try:
        market_usd = float(market_usd)
    except (TypeError, ValueError):
        return ""
    raw = max(market_usd * zar_rate * 1.10, 1.50)
    return math.ceil(raw * 2) / 2  # round UP to nearest R0.50


def main():
    only_pokemon = "--all" not in sys.argv

    zar_rate = get_usd_zar_rate()
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print("\nFetching groups for Card Sleeves category...")
    groups_data = get_json(f"{TCGCSV_BASE}/{CARD_SLEEVES_CATEGORY_ID}/groups")
    groups = groups_data.get("results", [])
    print(f"Found {len(groups)} group(s).\n")

    rows = []

    for i, group in enumerate(groups, 1):
        group_id = group["groupId"]
        group_name = group.get("name", "")
        group_abbr = group.get("abbreviation", "")

        print(f"[{i}/{len(groups)}] {group_name} (groupId={group_id})")

        try:
            products_data = get_json(f"{TCGCSV_BASE}/{CARD_SLEEVES_CATEGORY_ID}/{group_id}/products")
            products = products_data.get("results", [])
        except requests.RequestException as e:
            print(f"  FAILED to fetch products: {e}")
            continue

        time.sleep(REQUEST_DELAY_SECONDS)

        try:
            prices_data = get_json(f"{TCGCSV_BASE}/{CARD_SLEEVES_CATEGORY_ID}/{group_id}/prices")
            prices_by_product = {p["productId"]: p for p in prices_data.get("results", [])}
        except requests.RequestException as e:
            print(f"  FAILED to fetch prices: {e}")
            prices_by_product = {}

        time.sleep(REQUEST_DELAY_SECONDS)

        matched_this_group = 0
        for p in products:
            product_name = p.get("name", "")

            if only_pokemon and not is_pokemon_related(group_name, product_name):
                continue

            matched_this_group += 1
            price_info = prices_by_product.get(p["productId"], {})
            market_usd = price_info.get("marketPrice")

            extended = {e["name"]: e["value"] for e in p.get("extendedData", [])}

            rows.append({
                "group_id": group_id,
                "group_code": group_abbr,
                "group_name": group_name,
                "tcgcsv_group_id": group_id,
                "product_id": p.get("productId"),
                "name": product_name,
                "clean_name": p.get("cleanName", ""),
                "manufacturer": extended.get("Manufacturer", extended.get("Brand", "")),
                "pack_size": extended.get("Number of Items", ""),
                "sleeve_size": extended.get("Card Size", extended.get("Size", "")),
                "market_usd": market_usd if market_usd is not None else "",
                "low_usd": price_info.get("lowPrice", ""),
                "mid_usd": price_info.get("midPrice", ""),
                "high_usd": price_info.get("highPrice", ""),
                "pokebulk_zar": compute_pokebulk_zar(market_usd, zar_rate),
                "usd_zar_rate": zar_rate,
                "tcgplayer_image_url": p.get("imageUrl", ""),
                "tcgplayer_url": p.get("url", ""),
                "final_image_url": p.get("imageUrl", ""),  # no separate enrichment source for sleeves
                "tcgplayer_modified": p.get("modifiedOn", ""),
                "bible_built_at": built_at,
            })

        print(f"  -> {matched_this_group} matching product(s)")

    if not rows:
        print("\nNo matching products found.")
        return

    out_path = "pokemon_sleeves_bible.csv" if only_pokemon else "all_card_sleeves_bible.csv"
    fieldnames = list(rows[0].keys())

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} row(s) to {out_path}")


if __name__ == "__main__":
    main()
