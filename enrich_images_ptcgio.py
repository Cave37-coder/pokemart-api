"""
enrich_images_ptcgio.py
Fetches better images from pokemontcg.io for cards that only have
TCGPlayer 200w thumbnail images in the Bible.

Matches by ptcgio_set_id + card number.
Updates final_image_url and final_image_source columns.

USAGE:
  python enrich_images_ptcgio.py --bible pokebulk_bible_v4.csv --output pokebulk_bible_v5.csv
  python enrich_images_ptcgio.py --bible pokebulk_bible_v4.csv --output pokebulk_bible_v5.csv --set-code SM01
"""

import requests
import pandas as pd
import time
import argparse
from collections import defaultdict

API_KEY = "0ec1fcef-24b9-4239-b265-817f2c726099"
HEADERS = {"X-Api-Key": API_KEY}
BASE_URL = "https://api.pokemontcg.io/v2/cards"

def fetch_set_images(ptcgio_set_id):
    """Fetch all cards for a pokemontcg.io set, return dict of number -> image_url"""
    images = {}
    page = 1
    while True:
        try:
            r = requests.get(
                BASE_URL,
                headers=HEADERS,
                params={"q": f"set.id:{ptcgio_set_id}", "pageSize": 250, "page": page},
                timeout=30
            )
            data = r.json()
            cards = data.get("data", [])
            if not cards:
                break
            for card in cards:
                num = card.get("number", "")
                img = card.get("images", {}).get("large") or card.get("images", {}).get("small", "")
                if num and img:
                    images[num] = img
            if len(cards) < 250:
                break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error fetching {ptcgio_set_id} page {page}: {e}")
            break
    return images

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bible", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--set-code", help="Only enrich this set")
    args = parser.parse_args()

    print(f"Reading Bible: {args.bible}")
    df = pd.read_csv(args.bible, low_memory=False)
    print(f"Total rows: {len(df)}")

    # Find rows needing image enrichment
    needs_image = df[
        (df["final_image_source"] == "tcgplayer") &
        (df["ptcgio_set_id"].notna()) &
        (df["card_number"].notna())
    ]

    if args.set_code:
        needs_image = needs_image[needs_image["set_code"] == args.set_code]

    print(f"Rows needing image enrichment: {len(needs_image)}")

    # Group by ptcgio_set_id
    sets_to_process = needs_image.groupby("ptcgio_set_id")["set_code"].first().to_dict()
    print(f"Sets to fetch from pokemontcg.io: {len(sets_to_process)}")

    # Fetch images per set
    set_images = {}
    for ptcgio_id, set_code in sets_to_process.items():
        print(f"  Fetching {set_code} ({ptcgio_id})...", end=" ")
        images = fetch_set_images(ptcgio_id)
        set_images[ptcgio_id] = images
        print(f"{len(images)} cards")
        time.sleep(0.5)

    # Apply images to Bible
    updated = 0
    not_found = 0

    for idx, row in df.iterrows():
        if row.get("final_image_source") != "tcgplayer":
            continue
        ptcgio_id = row.get("ptcgio_set_id")
        if pd.isna(ptcgio_id) or not ptcgio_id:
            continue
        card_num = row.get("card_number")
        if pd.isna(card_num):
            continue

        images = set_images.get(ptcgio_id, {})
        if not images:
            continue

        # Try matching by card number
        # pokemontcg.io uses numbers like "001", "TG01", "SV1", "SM05" etc
        card_num_int = int(card_num)
        number_raw = str(row.get("number", "")).split("/")[0].strip()
        
        # Try multiple formats
        found_img = None
        formats_to_try = [
            number_raw,                  # "SM05", "TG01", "SV1" - raw format
            str(card_num_int),           # "5", "1"
            str(card_num_int).zfill(3),  # "005", "001"
            str(card_num_int).zfill(2),  # "05", "01"
        ]
        for fmt in formats_to_try:
            if fmt in images:
                found_img = images[fmt]
                break

        if found_img:
            df.at[idx, "final_image_url"] = found_img
            df.at[idx, "final_image_source"] = "pokemontcg_io"
            if "ptcg_image_small" in df.columns:
                df.at[idx, "ptcg_image_small"] = found_img
            updated += 1
        else:
            not_found += 1

    print(f"\nResults:")
    print(f"  Updated: {updated}")
    print(f"  Not found: {not_found}")
    print(f"  Remaining TCGPlayer: {len(df[df['final_image_source']=='tcgplayer'])}")

    df.to_csv(args.output, index=False)
    print(f"\nSaved: {args.output}")

if __name__ == "__main__":
    main()
