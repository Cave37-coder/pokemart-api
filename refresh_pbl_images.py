"""
refresh_pbl_images.py

Pitch Black (PBL) card images were originally scraped from Bulbapedia on
2026-07-07, before English scans existed -- so R2 currently holds the
Japanese Abyss Eye artwork. Bulbapedia has since been overwriting those
same file URLs with real English scans as prerelease/release content
becomes available (confirmed 2026-07-13 via file history on
File:MandibuzzPitchBlack50.jpg -- replaced in-place 2026-07-09, comment:
"English release").

This script re-downloads each Bulbapedia image fresh and overwrites the
matching R2 object at its EXISTING path. It does NOT touch the database --
image_url/image_small_url already point at the correct R2 paths, only the
file content behind those paths needs refreshing.

Run from C:\\Users\\texca\\pokemart-api with DATABASE_URL uncommented in .env:
    python manage.py shell -c "exec(open('refresh_pbl_images.py').read())"

Requires boto3 (already used by upload_to_r2.py / upload_set_images.py):
    pip install boto3 --break-system-packages

DRY RUN by default -- shows what would be downloaded/overwritten, changes
nothing. Set APPLY = True below to actually overwrite R2.
"""

import csv
import os
import time
import boto3
import requests
from botocore.config import Config
from products.models import PokemonProduct

APPLY = False  # flip to True once the dry-run output looks right

# Adjust if your bible CSV lives somewhere else locally.
BIBLE_CSV_PATH = "pokebulk_bible_v7.csv"

# Same R2 credentials as upload_to_r2.py / upload_set_images.py / migrate_prizepack_images_to_r2.py
R2_ENDPOINT = "https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com"
R2_ACCESS_KEY = "fdff88cee69c515cf67d4ae275d1bc72"
R2_SECRET_KEY = "e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f"
R2_BUCKET = "pokebulkcards"
R2_CDN = "https://images.pokebulk.co.za"

# Bulbapedia/Wikimedia blocks generic browser-impersonation UAs -- needs an
# honest, descriptive one identifying the client and a contact.
BULBA_HEADERS = {
    "User-Agent": "PokeBulkSA-ImageSync/1.0 (https://pokebulk.co.za; contact: enquiries@pokebulk.co.za)"
}


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def r2_key_from_url(url):
    """Extract the R2 object key from a full CDN URL, e.g.
    https://images.pokebulk.co.za/cards/PBL/704758_N.jpg -> cards/PBL/704758_N.jpg
    """
    if not url or R2_CDN not in url:
        return None
    return url.replace(R2_CDN + "/", "")


print("=" * 60)
print(f"Mode: {'APPLY (overwriting R2)' if APPLY else 'DRY RUN (no changes will be made)'}")
print("=" * 60)

# --- Step 1: load bible rows for PBL cards with a Bulbapedia image match ---
with open(BIBLE_CSV_PATH, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    bible_rows = [
        row for row in reader
        if row["set_code"] == "PBL" and row["card_number"] and row["bulba_image_url"]
    ]

print(f"Bible rows to consider: {len(bible_rows)}")

# Map tcgcsv product_id (int) -> bulba_image_url
product_to_bulba = {}
for row in bible_rows:
    try:
        pid = int(row["product_id"])
    except (TypeError, ValueError):
        continue
    product_to_bulba[pid] = row["bulba_image_url"]

print(f"Unique product_ids mapped: {len(product_to_bulba)}")

# --- Step 2: match against live DB rows to find the actual R2 keys in use ---
db_products = PokemonProduct.objects.filter(
    card_set__code="PBL",
    tcgcsv_product_id__in=list(product_to_bulba.keys()),
)
print(f"Matching PokemonProduct rows in DB: {db_products.count()}")

# Build list of (r2_key, bulba_url) pairs to refresh -- covers both
# image_url and image_small_url if they point at different R2 keys.
work_items = []
for p in db_products:
    bulba_url = product_to_bulba.get(p.tcgcsv_product_id)
    if not bulba_url:
        continue
    for field_val in (p.image_url, p.image_small_url):
        key = r2_key_from_url(field_val)
        if key:
            work_items.append((key, bulba_url, p.name, p.tcgcsv_product_id))

# De-duplicate (image_url and image_small_url are often identical)
seen_keys = set()
deduped = []
for key, bulba_url, name, pid in work_items:
    if key not in seen_keys:
        seen_keys.add(key)
        deduped.append((key, bulba_url, name, pid))
work_items = deduped

print(f"R2 objects to refresh: {len(work_items)}")
print()

if not work_items:
    print("Nothing to do -- no matching R2 keys found.")
else:
    print("Sample (first 5):")
    for key, bulba_url, name, pid in work_items[:5]:
        print(f"  {key}  <-  {bulba_url}  ({name}, product_id={pid})")
    print()

if APPLY and work_items:
    s3 = get_r2_client()
    image_cache = {}  # bulba_url -> bytes, since several R2 keys can share one source image
    ok, failed = 0, 0

    for i, (key, bulba_url, name, pid) in enumerate(work_items, start=1):
        try:
            if bulba_url not in image_cache:
                resp = requests.get(bulba_url, headers=BULBA_HEADERS, timeout=20)
                resp.raise_for_status()
                image_cache[bulba_url] = resp.content
                time.sleep(0.3)  # be polite to Bulbapedia's servers

            data = image_cache[bulba_url]
            content_type = "image/png" if key.lower().endswith(".png") else "image/jpeg"

            s3.put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)
            ok += 1
        except Exception as e:
            failed += 1
            print(f"  FAILED: {key} ({name}): {type(e).__name__}: {e}")

        if i % 25 == 0 or i == len(work_items):
            print(f"  processed {i}/{len(work_items)}... (ok={ok}, failed={failed})")

    print()
    print(f"Done. {ok} objects refreshed, {failed} failed.")
    print("Existing DB image_url/image_small_url values were NOT changed -- ")
    print("they already point at these same R2 keys, which now hold fresh images.")
    print("Hard-refresh (Ctrl+Shift+R) in the browser to bypass any cached copies.")
elif work_items:
    print("DRY RUN only -- no R2 objects were touched.")
    print("Review the sample above, then set APPLY = True and re-run to actually refresh them.")
