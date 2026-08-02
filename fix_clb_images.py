import django, os, time
import requests
import boto3
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

# Michael, 2026-08-02: same problem as fix_ccc_images.py solved for CCC --
# the CLB (Celebrations) set is hotlinked to https://images.pokemontcg.io/cel25/*.png,
# and that specific path is currently failing to load even though
# pokemontcg.io's own API still lists it as the card's image. Re-sources
# from TCGdex (confirmed reachable) and re-hosts on the same R2
# bucket/domain the rest of the catalog already uses.
#
# Credentials/PUBLIC_URL copied from fix_ccc_images.py -- the earlier
# fix_clb_images.py draft had stale/wrong R2 credentials copied from the
# older, apparently-abandoned upload_to_r2.py (different bucket URL,
# SignatureDoesNotMatch on every upload). This file uses the same working
# ones fix_ccc_images.py already proved out.

DRY_RUN = False  # dry run confirmed all 27 real cards resolve via TCGdex — applying now

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
}


def try_download(url, headers=None, retries=5):
    # TCGdex started read-timing-out partway through the first run -- looked
    # like rate-limiting from hitting it back-to-back rather than a real
    # missing image (the URLs that timed out are the same shape as ones that
    # succeeded seconds earlier). Retry with backoff before giving up.
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=25, headers=headers or {})
            if resp.status_code == 200:
                return resp
            last_err = resp.status_code
            # 404 means the asset genuinely isn't there -- retrying won't help.
            # Anything else (502, timeouts, etc.) is worth retrying.
            if last_err == 404:
                return last_err
        except Exception as e:
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
    return last_err


clb = CardSet.objects.get(code='CLB')
products = list(PokemonProduct.objects.filter(card_set=clb, is_active=True))
print(f"Total CLB products: {len(products)}\n")

to_update = []
still_broken = []

for p in products:
    if not p.card_number:
        still_broken.append((p, "no card_number -- not a numbered card (promo/code card), skipping"))
        continue

    # First confirm the current pokemontcg.io URL actually still fails
    result = try_download(p.image_url)
    if not isinstance(result, int) and not isinstance(result, str):
        print(f"  id={p.id} #{p.card_number} {p.name!r}: current image_url WORKS — leaving untouched")
        continue
    print(f"  id={p.id} #{p.card_number} {p.name!r}: current image_url failed ({result})")

    tcgdex_url = f"https://assets.tcgdex.net/en/swsh/swsh8/{p.card_number}/high.png"
    resp = try_download(tcgdex_url, headers=BROWSER_HEADERS)
    if isinstance(resp, int) or isinstance(resp, str):
        still_broken.append((p, f"TCGdex fallback also failed: {resp}"))
        continue

    print(f"    -> TCGdex fallback works: {tcgdex_url}")
    if not DRY_RUN:
        key = f"cards/CLB/CLB_{str(p.card_number).zfill(3)}.png"
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType="image/png")
        new_url = f"{PUBLIC_URL}/{key}"
        p.image_url = new_url
        p.image_small_url = new_url
        to_update.append(p)
    time.sleep(1.0)

if DRY_RUN:
    print(f"\nDRY RUN — nothing changed. Set DRY_RUN = False and rerun to apply.")
else:
    if to_update:
        PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=50)
    print(f"\nUpdated {len(to_update)} products.")

if still_broken:
    print(f"\n--- Still broken / skipped ({len(still_broken)}) ---")
    for p, reason in still_broken:
        print(f"  id={p.id} {p.name!r}: {reason}")
