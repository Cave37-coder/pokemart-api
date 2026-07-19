# PokeBulk SA - Download PBL Images (Serebii/Limitless) - ONE-SHOT, correct from the start
#
# Single script, replaces all prior fragmented PBL image scripts.
#
# For each unique tcgcsv product_id group in the bible (N/H/RH rows sharing
# one product_id share ONE photo):
#   1. Fetch the base image once (Limitless first, Serebii fallback).
#   2. Upload it to R2 ONCE at cards/PBL/{product_id}.jpg (no variant suffix --
#      confirmed 2026-07-13: image is shared by product_id, not by variant).
#   3. Update image_url/image_small_url on EVERY row in that product_id group
#      (N, H, and RH alike) to point at that one file.
#
# This does NOT create a separate _RH.jpg file. This does NOT touch rows
# whose product_id has no image source available (reported, not guessed).
#
# Credentials from environment variables:
#   $env:R2_ACCOUNT_ID = "229506129ad4206787dd4d3227608e17"
#   $env:R2_ACCESS_KEY_ID = "fdff88cee69c515cf67d4ae275d1bc72"
#   $env:R2_SECRET_ACCESS_KEY = "<secret>"
#
# Run from C:\Users\texca\pokemart-api with DATABASE_URL uncommented in .env:
#   python manage.py shell -c "exec(open('download_pbl_images_final.py').read())"
#
# DRY RUN by default -- prints the plan, touches nothing (no downloads,
# no R2 writes, no DB writes). Set APPLY = True below to actually run it.

import csv
import os
import re
import sys
import time
from io import BytesIO

import requests
import boto3
from botocore.config import Config
from PIL import Image

from products.models import PokemonProduct

APPLY = True  # flip to True once the dry-run output looks right

SET_CODE = 'PBL'
BIBLE_CSV_PATH = 'pokebulk_bible_v7.csv'  # adjust if it's elsewhere

R2_BUCKET = 'pokebulkcards'
PUBLIC_URL = 'https://images.pokebulk.co.za'
DELAY_SECS = 0.3

UA = 'PokeBulkSA-ImageSync/1.0 (https://pokebulk.co.za; contact: enquiries@pokebulk.co.za)'
SEREBII_SET_SLUG = 'pitchblack'
LIMITLESS_SET_CODE = 'PBL'


def get_r2_client():
    account_id = os.environ.get('R2_ACCOUNT_ID')
    access_key = os.environ.get('R2_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
    missing = [n for n, v in [('R2_ACCOUNT_ID', account_id),
                               ('R2_ACCESS_KEY_ID', access_key),
                               ('R2_SECRET_ACCESS_KEY', secret_key)] if not v]
    if missing:
        print('Missing required environment variable(s): ' + ', '.join(missing))
        sys.exit(1)
    endpoint_url = 'https://' + account_id + '.r2.cloudflarestorage.com'
    return boto3.client(
        's3', endpoint_url=endpoint_url,
        aws_access_key_id=access_key, aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'), region_name='auto',
    )


def get_limitless_image_url(card_number):
    url = f"https://limitlesstcg.com/cards/{LIMITLESS_SET_CODE}/{card_number}"
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Referer": "https://limitlesstcg.com/"}, timeout=20)
        if r.status_code != 200:
            return None
        m = re.search(
            r'(https://limitlesstcg\.nyc3\.cdn\.digitaloceanspaces\.com/tpci/'
            + re.escape(LIMITLESS_SET_CODE) + r'/[^"\'>\s]+\.png)', r.text
        )
        return m.group(1) if m else None
    except Exception:
        return None


def fetch_base_image(card_number):
    limitless_url = get_limitless_image_url(card_number)
    if limitless_url:
        try:
            r = requests.get(limitless_url, headers={"User-Agent": UA, "Referer": "https://limitlesstcg.com/"}, timeout=20)
            if r.status_code == 200 and r.content:
                return r.content
        except Exception:
            pass
    serebii_url = f"https://www.serebii.net/card/{SEREBII_SET_SLUG}/{card_number}.jpg"
    try:
        r = requests.get(serebii_url, headers={"User-Agent": UA, "Referer": "https://www.serebii.net/"}, timeout=20)
        if r.status_code == 200 and r.content and len(r.content) > 1000:
            return r.content
    except Exception:
        pass
    return None


def clean_jpeg_bytes(img_bytes):
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def extract_card_number(card_number_field):
    m = re.match(r'0*(\d+)', str(card_number_field).strip())
    return int(m.group(1)) if m else None


print("=" * 60)
print(f"Mode: {'APPLY (downloading + writing)' if APPLY else 'DRY RUN (no changes will be made)'}")
print("=" * 60)

with open(BIBLE_CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    bible_rows = [r for r in reader if r.get('set_code', '').strip() == SET_CODE and r.get('card_number', '').strip()]

print(f"Bible rows for {SET_CODE}: {len(bible_rows)}")

# Map product_id -> card_number (source number for fetching)
product_to_number = {}
for row in bible_rows:
    pid = row.get('product_id', '').strip()
    num = extract_card_number(row.get('card_number', ''))
    if pid and num is not None:
        product_to_number[pid] = num

print(f"Unique product_ids: {len(product_to_number)}")
print()

# Match against live DB: group PokemonProduct rows by tcgcsv_product_id
db_products = PokemonProduct.objects.filter(
    card_set__code=SET_CODE,
    tcgcsv_product_id__in=[int(p) for p in product_to_number if p.isdigit()],
)
from collections import defaultdict
db_groups = defaultdict(list)
for p in db_products:
    db_groups[p.tcgcsv_product_id].append(p)

print(f"Matching product_id groups in DB: {len(db_groups)}")
print(f"Total rows covered (N+H+RH combined): {sum(len(v) for v in db_groups.values())}")
print()

if APPLY:
    s3 = get_r2_client()

updated_rows = 0
uploaded_files = 0
no_source = []
failed = []

items = sorted(db_groups.items())
for i, (pid, rows) in enumerate(items, 1):
    card_number = product_to_number.get(str(pid))
    names = ', '.join(f"{r.variant_override or 'N'}" for r in rows)
    label = rows[0].name if rows else str(pid)

    if i % 25 == 0 or i == len(items):
        print(f"  [{i}/{len(items)}] product_id={pid} {label}")

    if card_number is None:
        no_source.append((pid, label, 'no card_number in bible'))
        continue

    key = f"cards/{SET_CODE}/{pid}.jpg"
    url = f"{PUBLIC_URL}/{key}"

    if not APPLY:
        print(f"  [DRY] product_id={pid} {label} -- variants: [{names}] -> one file: {key}")
        updated_rows += len(rows)
        continue

    base_bytes = fetch_base_image(card_number)
    if base_bytes is None:
        no_source.append((pid, label, 'not found on Limitless or Serebii'))
        continue

    try:
        clean_bytes = clean_jpeg_bytes(base_bytes)
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=clean_bytes, ContentType='image/jpeg')
        uploaded_files += 1
    except Exception as e:
        failed.append((pid, label, f'download/upload failed: {e}'))
        continue

    for r in rows:
        r.image_url = url
        r.image_small_url = url
        r.save(update_fields=['image_url', 'image_small_url'])
        updated_rows += 1

    time.sleep(DELAY_SECS)

print('\n' + '=' * 60)
print('Done!')
print(f"  {'Would update' if not APPLY else 'Updated'} rows: {updated_rows}")
if APPLY:
    print(f"  R2 files uploaded (one per product_id): {uploaded_files}")
print(f"  No source image found: {len(no_source)}")
print(f"  Failed: {len(failed)}")
if no_source:
    print("\n  No source found:")
    for pid, label, reason in no_source[:20]:
        print(f"    [{pid}] {label} -- {reason}")
if failed:
    print("\n  Failures:")
    for pid, label, reason in failed:
        print(f"    [{pid}] {label} -- {reason}")
print('=' * 60)
