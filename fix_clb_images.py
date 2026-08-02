import django, os, re, time
import requests
import boto3
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

# Michael, 2026-08-02: the CLB (Celebrations) set is hotlinked to
# https://images.pokemontcg.io/cel25/*.png, and that specific path is
# currently failing to load even though pokemontcg.io's own API still
# lists it as the card's image.
#
# CORRECTION 2026-08-02: the first version of this script sourced
# replacements from TCGdex (assets.tcgdex.net/en/swsh/swsh8/<num>/high.png).
# That was WRONG -- swsh8 on TCGdex is Fusion Strike, not Celebrations, so
# it silently uploaded a completely different Pokemon's art onto several
# CLB products (Michael caught this: Pikachu's listing was showing
# Breloom's card, Flying Pikachu VMAX was showing Pansage, etc). Confirmed
# via the pkmn.gg reference screenshot that the images were wrong, not a
# rendering issue on pokebulk's side.
#
# This version sources from Serebii instead (per Michael's explicit
# preference -- "image download should come Serebii, they have the biggest
# collection of images"), using slug "celebrations" -- confirmed correct by
# actually reading the card page content (not just that the URL responds):
# https://www.serebii.net/card/celebrations/005.shtml genuinely renders
# "Pikachu, 60 HP, Gnaw, Thunder Jolt, illustrator Mitsuhiro Arita", which
# matches pokemontcg.io's own data for cel25-5 exactly. Every card number
# 1-25 on that page's set list matches this catalog's CLB card names too.
#
# To not repeat the TCGdex mistake, this script VERIFIES the Serebii page
# actually names the expected Pokemon/card before trusting its image --
# it does not blindly trust a number-based URL match this time.
#
# Uses a fresh .jpg key per card (not the old fix_clb_images .png keys from
# the aborted TCGdex run), so there's no stale-CDN-cache collision with the
# wrong images that were briefly live.

DRY_RUN = False  # 25/27 verified against real Serebii page content -- applying now

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
SEREBII_SLUG = "celebrations"


def clean_name(name):
    # Strip parenthetical suffixes Michael's catalog adds for internal
    # disambiguation ("(Secret)", "(Full Art)") that Serebii's page title
    # won't contain -- compare on the base Pokemon/card name only.
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name or '').strip()
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

    img_url = f"https://www.serebii.net/card/{SEREBII_SLUG}/{card_number}.jpg"
    img_resp = try_get(img_url)
    if isinstance(img_resp, (int, str)):
        return None, f"image fetch failed ({img_resp}): {img_url}"

    return img_resp.content, None


clb = CardSet.objects.get(code='CLB')
products = list(PokemonProduct.objects.filter(card_set=clb, is_active=True))
print(f"Total CLB products: {len(products)}\n")

to_update = []
still_broken = []

for p in products:
    if not p.card_number:
        still_broken.append((p, "no card_number -- not a numbered card (promo/code card), skipping"))
        continue

    # NOT checking "does the current image_url return 200" anymore -- that's
    # exactly the check that let the wrong TCGdex images slip through last
    # time (a 200 response to a WRONG image is still a 200). Every numbered
    # CLB card gets unconditionally re-verified and re-sourced from Serebii,
    # regardless of what's currently stored.
    print(f"  id={p.id} #{p.card_number} {p.name!r}: re-sourcing from Serebii...")

    img_bytes, err = verify_and_fetch(p.card_number, p.name)
    if err:
        still_broken.append((p, f"Serebii: {err}"))
        continue

    print(f"    -> Serebii VERIFIED match, image fetched ({len(img_bytes)} bytes)")
    if not DRY_RUN:
        key = f"cards/CLB/CLB_{str(p.card_number).zfill(3)}_serebii.jpg"
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
