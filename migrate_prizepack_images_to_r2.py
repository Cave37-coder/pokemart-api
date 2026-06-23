"""
Migrate Prize Pack images from TCGplayer's CDN to our own R2 bucket, so
PRIZEPACK is consistent with every other set on the site (self-hosted via
images.pokebulk.co.za rather than hotlinking an external CDN long-term).

Run from C:\\Users\\texca\\pokemart-api with DATABASE_URL uncommented in .env:
    python manage.py shell -c "exec(open('migrate_prizepack_images_to_r2.py').read())"

Requires boto3:
    pip install boto3 --break-system-packages

Fill in your R2 credentials below (same ones used for upload_to_r2.py /
upload_set_images.py) before running.
"""
import time
import requests
import boto3
from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

# --- R2 credentials (confirmed working as of the logo/symbol upload session) ---
R2_ACCESS_KEY_ID = "fdff88cee69c515cf67d4ae275d1bc72"
R2_SECRET_ACCESS_KEY = "e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f"
R2_ENDPOINT = "https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com"
R2_BUCKET = "pokebulkcards"
PUBLIC_URL = "https://images.pokebulk.co.za"  # custom domain, NOT the old r2.dev URL

if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
    print("!! Fill in R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY at the top of this file before running.")
else:
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

    def sanitize_key(pb_id: str) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in pb_id)
        return f"cards/PRIZEPACK/{safe}.jpg"

    pp = CardSet.objects.get(id=143)  # PRIZEPACK
    qs = PokemonProduct.objects.filter(
        card_set=pp,
        image_url__startswith="https://tcgplayer-cdn.tcgplayer.com/",
    )
    total = qs.count()
    print(f"Total Prize Pack images to migrate: {total}")

    uploaded = 0
    failed = 0
    to_update = []

    TCG_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://www.tcgplayer.com/",
    }

    for i, p in enumerate(qs.iterator(), 1):
        if i % 100 == 0:
            print(f"Progress: {i}/{total} | Uploaded:{uploaded} Failed:{failed}")

        key = sanitize_key(p.pb_id)

        try:
            resp = requests.get(p.image_url, timeout=15, headers=TCG_HEADERS)
            if resp.status_code != 200:
                time.sleep(1.5)
                resp = requests.get(p.image_url, timeout=15, headers=TCG_HEADERS)
            if resp.status_code != 200:
                failed += 1
                print(f"  FAILED (status {resp.status_code}): id={p.id} {p.name[:40]!r} url={p.image_url}")
                continue
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType=content_type)

            new_url = f"{PUBLIC_URL}/{key}"
            p.image_url = new_url
            p.image_small_url = new_url
            to_update.append(p)
            uploaded += 1
        except Exception as e:
            failed += 1
            print(f"  FAILED (exception): id={p.id} {p.name[:40]!r} | {e}")
            time.sleep(0.5)
            continue

        time.sleep(0.15)  # be polite to TCGplayer's CDN

        if len(to_update) >= 50:
            try:
                connection.ensure_connection()
                PokemonProduct.objects.bulk_update(to_update, ["image_url", "image_small_url"], batch_size=200)
                print(f"  Saved {len(to_update)} records...")
                to_update = []
            except Exception as e:
                print(f"  DB save error, retrying after backoff: {e}")
                connection.close()
                time.sleep(2)

    if to_update:
        try:
            PokemonProduct.objects.bulk_update(to_update, ["image_url", "image_small_url"], batch_size=200)
        except Exception as e:
            print(f"  Final save error: {e}")

    print(f"\nDONE | Uploaded:{uploaded} Failed:{failed} of Total:{total}")
