"""
WotC exact images (2026-11-06) -- Michael: "Can we update the card images to
exactly each card?"

What I found checking every source (TCGplayer, Serebii, pokemontcg.io,
PkmnCards, Limitless): the standard scans of WotC cards are all the
1st EDITION print (stamp under the art). Only TCGplayer's own groups give the
right print per product:
  * TCGCSV group 1663 / JU / FO / TR / Gym / Neo products  -> 1st Edition scan
  * TCGCSV group 604 (Base Set Unlimited) products          -> Unlimited scan (drop shadow, no stamp)

So this script sets, from TCGplayer's high-res image, copied into R2:
  1. every 1st Edition row (variant FE) in BSS, JU, FO, TR, G1, G2, N1-N4
  2. every row in BS (Base Set Unlimited) -- these were showing a 1st
     Edition Serebii scan, which is the wrong print.
Shadowless (BSS N/H) and the Unlimited rows of JU..N4 are NOT touched: no
source has a no-stamp scan for them (see the chat for the options).

Dry run by default (prints what it would change, writes nothing). To apply:
    $env:LIVE="1"; python manage.py shell -c "exec(open('wotc_exact_images.py').read())"; Remove-Item Env:LIVE
Dry run:
    python manage.py shell -c "exec(open('wotc_exact_images.py').read())"
Resumable: a row already pointing at its wotc_exact key is skipped.
"""
import os
import time
import requests
import boto3
from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct

LIVE = os.environ.get("LIVE") == "1"

R2_ACCESS_KEY_ID = "fdff88cee69c515cf67d4ae275d1bc72"
R2_SECRET_ACCESS_KEY = "e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f"
R2_ENDPOINT = "https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com"
R2_BUCKET = "pokebulkcards"
PUBLIC_URL = "https://images.pokebulk.co.za"

s3 = boto3.client(
    "s3", endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"), region_name="auto",
)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.tcgplayer.com/",
}

FIRST_ED_SETS = ["BSS", "JU", "FO", "TR", "G1", "G2", "N1", "N2", "N3", "N4"]


def candidates(pid):
    base = f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}"
    return [f"{base}_in_1000x1000.jpg", f"{base}_400w.jpg", f"{base}_200w.jpg"]


def download(pid):
    for url in candidates(pid):
        try:
            r = requests.get(url, timeout=20, headers=BROWSER_HEADERS)
            if r.status_code == 200 and len(r.content) > 2000:
                return r, url
        except Exception:
            pass
        time.sleep(0.2)
    return None, None


def key_for(p):
    safe_set = "".join(c if c.isalnum() else "_" for c in p.card_set.code)
    safe_pb = "".join(c if c.isalnum() else "_" for c in p.pb_id)
    return f"cards/{safe_set}/wotc_exact/{safe_pb}.jpg"


targets = list(
    PokemonProduct.objects.filter(card_set__code__in=FIRST_ED_SETS, variant_override="FE",
                                  tcgcsv_product_id__isnull=False).select_related("card_set")
) + list(
    PokemonProduct.objects.filter(card_set__code="BS", tcgcsv_product_id__isnull=False).select_related("card_set")
)
print(f"{'LIVE' if LIVE else 'DRY RUN'} -- {len(targets)} rows to check")

done = skipped = 0
failed = []
to_update = []
by_set = {}
for i, p in enumerate(targets, 1):
    key = key_for(p)
    new_url = f"{PUBLIC_URL}/{key}"
    if p.image_url == new_url:
        skipped += 1
        continue
    by_set[p.card_set.code] = by_set.get(p.card_set.code, 0) + 1
    if not LIVE:
        if by_set[p.card_set.code] <= 2:
            print(f"  [DRY] {p.card_set.code} #{p.card_number} {p.name} {p.variant_override}: "
                  f"{p.image_url}  ->  {new_url}  (from TCGplayer pid {p.tcgcsv_product_id})")
        done += 1
        continue
    resp, src = download(p.tcgcsv_product_id)
    if not resp:
        failed.append((p.id, p.card_set.code, p.name, p.tcgcsv_product_id))
        continue
    try:
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content,
                      ContentType=resp.headers.get("Content-Type", "image/jpeg"))
    except Exception as e:
        failed.append((p.id, p.card_set.code, p.name, f"R2: {e}"))
        continue
    p.image_url = new_url
    p.image_small_url = new_url
    to_update.append(p)
    done += 1
    if len(to_update) >= 50:
        connection.ensure_connection()
        PokemonProduct.objects.bulk_update(to_update, ["image_url", "image_small_url"], batch_size=200)
        to_update = []
        print(f"  ...{i}/{len(targets)} done={done} failed={len(failed)}")
    time.sleep(0.08)

if to_update:
    PokemonProduct.objects.bulk_update(to_update, ["image_url", "image_small_url"], batch_size=200)

print(f"\n{'LIVE' if LIVE else 'DRY RUN'} DONE | {'updated' if LIVE else 'would update'}={done} "
      f"already-done={skipped} failed={len(failed)}")
print("Per set:", by_set)
for f in failed[:40]:
    print("  FAILED", f)
