"""
Migrates ALL remaining non-R2 product images (tcgplayer-cdn.tcgplayer.com and
images.pokemontcg.io, ~8,276 products) to R2, so the whole catalog is
self-hosted and immune to third-party CDN outages/blocks/403s like the one
that just hit Bulbasaur.

Naturally resumable: only touches products NOT already on images.pokebulk.co.za,
so if interrupted, just rerun — already-migrated rows are skipped automatically.

Run from C:\\Users\\texca\\pokemart-api with DATABASE_URL uncommented:
    python manage.py shell -c "exec(open('migrate_sitewide_images_to_r2.py').read())"
"""
import time
import requests
import boto3
from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct

R2_ACCESS_KEY_ID = "fdff88cee69c515cf67d4ae275d1bc72"
R2_SECRET_ACCESS_KEY = "e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f"
R2_ENDPOINT = "https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com"
R2_BUCKET = "pokebulkcards"
PUBLIC_URL = "https://images.pokebulk.co.za"

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.tcgplayer.com/",
}


def sanitize_key(set_code: str, pb_id: str) -> str:
    safe_set = "".join(c if c.isalnum() else "_" for c in (set_code or "UNKNOWN"))
    safe_pb = "".join(c if c.isalnum() else "_" for c in pb_id)
    return f"cards/{safe_set}/{safe_pb}.jpg"


def try_download(url):
    try:
        resp = requests.get(url, timeout=15, headers=BROWSER_HEADERS)
        if resp.status_code == 200:
            return resp
    except Exception:
        pass
    return None


qs = PokemonProduct.objects.filter(
    image_url__regex=r'^https://(tcgplayer-cdn\.tcgplayer\.com|images\.pokemontcg\.io)/'
).select_related('card_set')
total = qs.count()
print(f"Total products to migrate: {total}")

uploaded = 0
failed = []
to_update = []

for i, p in enumerate(qs.iterator(), 1):
    if i % 100 == 0:
        print(f"Progress: {i}/{total} | Uploaded:{uploaded} Failed:{len(failed)}")

    set_code = p.card_set.code if p.card_set else None
    key = sanitize_key(set_code, p.pb_id)
    base_url = p.image_url

    candidates = [base_url]
    if "_200w.jpg" in base_url:
        candidates.append(base_url.replace("_200w.jpg", "_400w.jpg"))
        candidates.append(base_url.replace("_200w.jpg", ".jpg"))

    resp = None
    for url in candidates:
        resp = try_download(url)
        if resp:
            break
        time.sleep(0.2)

    if not resp:
        failed.append((p.id, p.name, base_url))
        continue

    try:
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType=content_type)
        new_url = f"{PUBLIC_URL}/{key}"
        p.image_url = new_url
        p.image_small_url = new_url
        to_update.append(p)
        uploaded += 1
    except Exception as e:
        failed.append((p.id, p.name, f"R2 upload error: {e}"))
        continue

    time.sleep(0.08)

    if len(to_update) >= 50:
        try:
            connection.ensure_connection()
            PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=200)
            to_update = []
        except Exception as e:
            print(f"  DB save error, retrying after backoff: {e}")
            connection.close()
            time.sleep(2)

if to_update:
    try:
        PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=200)
    except Exception as e:
        print(f"  Final save error: {e}")

print(f"\nDONE | Uploaded:{uploaded} Failed:{len(failed)} of Total:{total}")
if failed:
    print(f"\n--- Failures (first 30 of {len(failed)}) ---")
    for fid, fname, furl in failed[:30]:
        print(f"  id={fid} {fname!r} | {furl}")
