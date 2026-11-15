import django, os, re, time
import requests
import boto3
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from products.models import PokemonProduct, CardSet

# Michael, 2026-08-04: "We have a ton of the Promo cards not showing
# images, use serebii to download all" -- same treatment as the CLB
# (Celebrations) fix from 2026-08-02, same reasoning ("image download
# should come Serebii, they have the biggest collection of images"), same
# safety net: EVERY card is re-verified against the actual Serebii page
# content (not just "does a URL respond 200") before its image is trusted,
# so a wrong-Pokemon mixup (like the TCGdex mistake during the CLB fix)
# can't slip through silently.
#
# Set: SVP (SV Promos). Serebii slug + per-card page pattern confirmed by
# actually reading https://serebii.net/card/svpromos/001.shtml -> "Sprigatito",
# 002 -> "Fuecoco", 003 -> "Quaxly", etc. -- matches this catalog's SVP names.

DRY_RUN = True  # review the VERIFIED matches below, then set to False and rerun

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

UA = "PokeBulkSA/1.0.0 (enquiries@pokebulk.co.za)"
SEREBII_SLUG = "svpromos"


def clean_name(name):
    # Strip parenthetical suffixes this catalog adds for internal
    # disambiguation ("(Secret)", "(Full Art)", "(Staff)") that Serebii's
    # page won't contain, and normalise "-EX"/"-GX" hyphenation and case so
    # "Mimikyu-EX" and "Mimikyu ex" compare equal.
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name or '').strip()
    name = name.replace('-', ' ')
    name = re.sub(r'\s+', ' ', name)
    return name.lower()


def try_get(url, retries=4, timeout=20):
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
            if resp.status_code == 200:
                return resp
            last_err = resp.status_code
            if last_err == 404:
                return last_err
        except Exception as e:
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(2 * (attempt + 1))
    return last_err


def verify_and_fetch(card_number, expected_name):
    """Returns (image_bytes, None) on a verified match, or (None, reason) otherwise."""
    padded = str(int(card_number)).zfill(3)
    page_url = f"https://www.serebii.net/card/{SEREBII_SLUG}/{padded}.shtml"
    page_resp = try_get(page_url)
    if isinstance(page_resp, (int, str)):
        return None, f"page fetch failed: {page_resp}"

    page_text = page_resp.text.lower()
    expected = clean_name(expected_name)
    if not expected or expected not in page_text:
        return None, f"expected name {expected_name!r} not found on {page_url}"

    # Image filename convention differs slightly between Serebii sets --
    # try unpadded first (matches the CLB fix), fall back to zero-padded.
    for candidate in (str(int(card_number)), padded):
        img_url = f"https://www.serebii.net/card/{SEREBII_SLUG}/{candidate}.jpg"
        img_resp = try_get(img_url)
        if not isinstance(img_resp, (int, str)):
            return img_resp.content, None

    return None, f"image fetch failed for both padded and unpadded numbers at {page_url}"


svp = CardSet.objects.get(code='SVP')
products = list(PokemonProduct.objects.filter(card_set=svp, is_active=True))
print(f"Total SVP products: {len(products)}\n")

to_update = []
still_broken = []

for p in products:
    if not p.card_number:
        still_broken.append((p, "no card_number -- not a numbered card, skipping"))
        continue

    print(f"  id={p.id} #{p.card_number} {p.name!r}: re-sourcing from Serebii...")

    img_bytes, err = verify_and_fetch(p.card_number, p.name)
    if err:
        still_broken.append((p, f"Serebii: {err}"))
        continue

    print(f"    -> Serebii VERIFIED match, image fetched ({len(img_bytes)} bytes)")
    if not DRY_RUN:
        key = f"cards/SVP/SVP_{str(p.card_number).zfill(3)}_serebii.jpg"
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=img_bytes, ContentType="image/jpeg")
        new_url = f"{PUBLIC_URL}/{key}"
        p.image_url = new_url
        p.image_small_url = new_url
        to_update.append(p)
    time.sleep(1.0)

if DRY_RUN:
    print(f"\nDRY RUN — nothing changed. Check every 'VERIFIED match' line above against the real card, then set DRY_RUN = False and rerun.")
else:
    if to_update:
        PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=50)
    print(f"\nUpdated {len(to_update)} products.")

if still_broken:
    print(f"\n--- Still broken / skipped ({len(still_broken)}) ---")
    for p, reason in still_broken:
        print(f"  id={p.id} {p.name!r}: {reason}")
