"""
fetch_ball_variants.py
Fetches ball variant products from TCGCSV for ASC, BLK, WHT, PRE
and adds them as new rows to the Bible CSV.

Ball variants are separate productIds in TCGCSV products endpoint
(not subtypes of existing products).
"""
import os
import sys
import requests
import pandas as pd
from decimal import Decimal
import math
import time

HEADERS = {"User-Agent": "PokeBulkSA/1.0"}
TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
MARKUP = 1.10

# Sets with ball variants and their groupIds
BALL_VARIANT_SETS = {
    "ASC": 24541,
    "BLK": 24325,
    "WHT": 24326,
    "PRE": 23821,
}

# Map product name suffix -> variant_override code
BALL_VARIANT_MAP = {
    "Poke Ball":             "PB",
    "Master Ball":           "MB",
    "Love Ball":             "LB",
    "Friend Ball":           "FB",
    "Quick Ball":            "QB",
    "Ultra Ball":            "UB",
    "Dusk Ball":             "DB",
    "Team Rocket":           "TR",
    "Special":               "SE",
    "Energy Symbol Pattern": "RH",  # Energy cards with pattern = RH
    "Poke Ball Pattern":     "PBP",
    "Master Ball Pattern":   "MBP",
    "Holiday Calendar":      "SE",
}

# Variants to skip - sealed products not cards
SKIP_VARIANTS = {"Exclusive", "Sam's Club", "Dollar General Exclusive",
                 "48 ct", "Holiday Calendar Exclusive"}

def zar_price(usd, rate):
    if not usd:
        return 1.50
    raw = float(usd) * rate * MARKUP
    val = max(1.50, raw)
    return math.ceil(val * 2) / 2

def get_rate():
    for url in ["https://api.exchangerate-api.com/v4/latest/USD",
                "https://open.er-api.com/v6/latest/USD"]:
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            rates = data.get("rates") or data.get("conversion_rates", {})
            if "ZAR" in rates:
                return float(rates["ZAR"])
        except:
            continue
    return 16.50  # fallback

def extract_variant(name):
    """Extract variant from product name like 'Erika Oddish (Poke Ball)'"""
    if '(' in name and name.endswith(')'):
        variant_part = name[name.rfind('(')+1:-1].strip()
        return variant_part
    return None

def parse_card_number(raw):
    import re
    if not raw:
        return None
    raw = str(raw).split('/')[0].strip()
    try:
        return int(raw)
    except ValueError:
        m = re.match(r'^[A-Za-z]+0*(\d+)$', raw)
        return int(m.group(1)) if m else None

def ext(extended_data, field_name):
    for item in extended_data:
        if item.get("name") == field_name:
            return item.get("value", "")
    return ""

def main(bible_path, output_path):
    print(f"Reading Bible: {bible_path}")
    df = pd.read_csv(bible_path, low_memory=False)
    existing_pids = set(df['product_id'].dropna().astype(int).tolist())
    print(f"Bible rows: {len(df)} | Existing product IDs: {len(existing_pids)}")

    rate = get_rate()
    print(f"USD/ZAR rate: {rate:.2f}")

    new_rows = []

    for set_code, group_id in BALL_VARIANT_SETS.items():
        print(f"\nFetching {set_code} (group {group_id})...")

        # Get products
        r = requests.get(f"{TCGCSV_BASE}/{group_id}/products",
                        headers=HEADERS, timeout=30)
        products = r.json().get("results", [])

        # Get prices
        rp = requests.get(f"{TCGCSV_BASE}/{group_id}/prices",
                         headers=HEADERS, timeout=30)
        prices = {}
        for row in rp.json().get("results", []):
            pid = row.get("productId")
            sub = row.get("subTypeName", "")
            mkt = row.get("marketPrice") or row.get("lowPrice")
            if pid and mkt:
                prices[pid] = mkt

        # Find ball variant products
        found = 0
        skipped = 0
        for p in products:
            pid = p.get("productId")
            name = (p.get("name") or "").strip()

            # Skip if already in Bible
            if pid in existing_pids:
                skipped += 1
                continue

            # Extract variant from name
            variant_name = extract_variant(name)
            if not variant_name:
                continue

            # Skip sealed products
            if variant_name in SKIP_VARIANTS:
                continue

            # Map to variant code
            variant_code = BALL_VARIANT_MAP.get(variant_name)
            if not variant_code:
                continue

            # Get card details
            ext_data = p.get("extendedData", [])
            number_raw = ext(ext_data, "Number")
            rarity_raw = ext(ext_data, "Rarity")
            card_number = parse_card_number(number_raw)
            image_url = p.get("imageUrl", "")
            usd = prices.get(pid)
            zar = zar_price(usd, rate)

            # Base name (strip variant suffix)
            base_name = name[:name.rfind('(')].strip() if '(' in name else name

            new_rows.append({
                "group_id": group_id,
                "set_code": set_code,
                "era": "Mega Evolution" if set_code in ["ASC","MEG","PFL","POR","CRI"] else "Scarlet & Violet",
                "set_name": {"ASC":"Ascended Heroes","BLK":"Black Bolt",
                            "WHT":"White Flare","PRE":"Prismatic Evolutions"}.get(set_code,""),
                "product_id": pid,
                "name": name,
                "clean_name": base_name,
                "number": number_raw,
                "card_number": card_number,
                "rarity": rarity_raw,
                "variant": variant_name,
                "market_usd": usd,
                "pokebulk_zar": zar,
                "usd_zar_rate": rate,
                "tcgplayer_image_url": image_url,
                "final_image_url": image_url,
                "final_image_source": "tcgplayer",
                "is_card": True,
            })
            found += 1

        print(f"  Found: {found} new ball variant rows | Skipped existing: {skipped}")
        time.sleep(0.5)

    print(f"\nTotal new rows to add: {len(new_rows)}")

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([df, new_df], ignore_index=True)
        combined.to_csv(output_path, index=False)
        print(f"Saved Bible v2 with ball variants: {output_path}")
        print(f"Total rows: {len(combined)}")
    else:
        print("No new rows found")
        df.to_csv(output_path, index=False)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bible', required=True, help='Input Bible CSV path')
    parser.add_argument('--output', required=True, help='Output Bible CSV path')
    args = parser.parse_args()
    main(args.bible, args.output)
