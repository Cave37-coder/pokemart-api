import time
import requests
import boto3
from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

DRY_RUN = False  # confirmed via dry run — applying now

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


def try_download(url, headers=None):
    try:
        resp = requests.get(url, timeout=15, headers=headers or {})
        if resp.status_code == 200:
            return resp
        return resp.status_code
    except Exception as e:
        return str(e)


ccc = CardSet.objects.get(code='CCC')
products = list(PokemonProduct.objects.filter(card_set=ccc))
print(f"Total CCC products: {len(products)}\n")

to_update = []
still_broken = []

for p in products:
    # First confirm the current pokemontcg.io URL actually fails
    result = try_download(p.image_url)
    if not isinstance(result, int) and not isinstance(result, str):
        print(f"  id={p.id} {p.name!r}: pokemontcg.io WORKS — leaving untouched")
        continue
    print(f"  id={p.id} {p.name!r}: pokemontcg.io failed ({result})")

    # Fall back to TCGplayer CDN using the tcgcsv id in pb_id
    if not p.pb_id.startswith('TCGCSV-'):
        still_broken.append((p, 'no tcgcsv id in pb_id to fall back on'))
        continue
    tcg_id = p.pb_id.replace('TCGCSV-', '', 1)
    tcg_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{tcg_id}_200w.jpg"
    resp = try_download(tcg_url, headers=BROWSER_HEADERS)
    if isinstance(resp, int) or isinstance(resp, str):
        still_broken.append((p, f'tcgplayer fallback also failed: {resp}'))
        continue

    print(f"    -> tcgplayer fallback works: {tcg_url}")
    if not DRY_RUN:
        safe_pb = "".join(c if c.isalnum() else "_" for c in p.pb_id)
        key = f"cards/CCC/{safe_pb}.jpg"
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType=content_type)
        new_url = f"{PUBLIC_URL}/{key}"
        p.image_url = new_url
        p.image_small_url = new_url
        to_update.append(p)
    time.sleep(0.15)

if DRY_RUN:
    print(f"\nDRY RUN — nothing changed. Set DRY_RUN = False and rerun to apply.")
else:
    if to_update:
        PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=50)
    print(f"\nUpdated {len(to_update)} products.")

if still_broken:
    print(f"\n--- Still broken after fallback attempt ({len(still_broken)}) ---")
    for p, reason in still_broken:
        print(f"  id={p.id} {p.name!r}: {reason}")
