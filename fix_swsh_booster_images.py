import django, os, re, time
import requests
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

# Michael, 2026-08-04: "maybe we should run similar for SWSH sets, there are
# missing images there too" -- same verified Serebii re-source as the promo
# batch, extended to the 21 SWSH-era BOOSTER sets (not the SWSH promos,
# already fixed). Slugs confirmed by reading Serebii's actual SWSH Series
# index page (serebii.net/card/swsh.shtml).
#
# Subset codes (TG/GG/SV = Trainer Gallery / Galarian Gallery / Shiny Vault)
# map to the SAME Serebii slug as their parent set, since Serebii hosts them
# on the same set page, just with different card numbers -- the per-card
# name verification below will simply report "broken" for anything whose
# number format doesn't line up, exactly like the promo batch did for a
# handful of edge cases. No risk of a silent wrong-image mixup either way.
#
# Same safety net every image-fix script this session has used: a card's
# image is NEVER trusted just because a URL returns 200 -- its Serebii page
# must actually contain the expected Pokemon/card name first.

DRY_RUN = False  # review VERIFIED/broken output, then set False and rerun

SET_SLUGS = {
    'SSH':     'swordshield',
    'RCL':     'rebelclash',
    'DAA':     'darknessablaze',
    'VIV':     'vividvoltage',
    'SHF':     'shiningfates',
    'SHFSV':   'shiningfates',
    'BST':     'battlestyles',
    'CRE':     'chillingreign',
    'EVS':     'evolvingskies',
    'FST':     'fusionstrike',
    'BRS':     'brilliantstars',
    'BRSTG':   'brilliantstars',
    'ASR':     'astralradiance',
    'ASRTG':   'astralradiance',
    'PGO':     'pokemongo',
    'LOR':     'lostorigin',
    'LORTG':   'lostorigin',
    'SIT':     'silvertempest',
    'SITTG':   'silvertempest',
    'CRZ':     'crownzenith',
    'CRZGG':   'crownzenith',
}

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

TRAIL_BRACKET = re.compile(r'\s*\[[^\]]*\]\s*$')
TRAIL_PAREN = re.compile(r'\s*\([^)]*\)\s*$')
TRAIL_SETNUM = re.compile(r'\s*-\s*\d+/\d+\s*$')
TRAIL_SLASHCODE = re.compile(r'\s*-\s*\d+/[A-Za-z0-9-]+\s*$')
TRAIL_DASHCODE = re.compile(r'\s*-\s*[A-Za-z]{0,6}\d+[A-Za-z]{0,2}\s*$')
SUFFIX_LVX = re.compile(r'\s+lv\.?\s*x$', re.IGNORECASE)  # DP-era "LV.X" tag isn't part of the printed page text


def strip_trailing_decorations(name):
    prev = None
    while prev != name:
        prev = name
        name = TRAIL_BRACKET.sub('', name)
        name = TRAIL_PAREN.sub('', name)
        name = TRAIL_SETNUM.sub('', name)
        name = TRAIL_SLASHCODE.sub('', name)
        name = TRAIL_DASHCODE.sub('', name)
    return name.strip()


def clean_name(name):
    name = strip_trailing_decorations((name or '').strip())
    name = SUFFIX_LVX.sub('', name)
    name = re.sub(r'\s+', ' ', name)
    return name.lower()


def try_get(url, retries=3, timeout=20):
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


def verify_and_fetch(slug, card_number, expected_name):
    n = int(card_number)
    # Shining Fates' "Shiny Vault" reissue subset (numbers 74+ in this
    # catalog, i.e. every SHFSV product plus SHF #74+) lives on Serebii under
    # a totally different URL scheme than the base set: H{n}.shtml / h{n}.jpg
    # (capital H, no zero-padding, lowercase h for the image) instead of
    # {n:03}.shtml. Confirmed by fetching serebii.net/card/shiningfates/H117.shtml
    # directly -- that's Grimmsnarl VMAX, matching card_number=117 in this DB.
    # This is why every SHFSV card 404'd on the first dry run: wrong URL
    # pattern for that subset, not missing Serebii content.
    if slug == 'shiningfates' and n >= 74:
        page_url = f"https://www.serebii.net/card/{slug}/H{n}.shtml"
        page_resp = try_get(page_url)
        if isinstance(page_resp, (int, str)):
            return None, f"page fetch failed: {page_resp} ({page_url})"
        page_text = page_resp.text.lower()
        expected = clean_name(expected_name)
        if not expected or expected not in page_text:
            return None, f"expected name {expected_name!r} not found on {page_url}"
        img_url = f"https://www.serebii.net/card/{slug}/h{n}.jpg"
        img_resp = try_get(img_url)
        if not isinstance(img_resp, (int, str)):
            return img_resp.content, None
        return None, f"image fetch failed at {page_url}"

    padded = str(n).zfill(3)
    page_url = f"https://www.serebii.net/card/{slug}/{padded}.shtml"
    page_resp = try_get(page_url)
    if isinstance(page_resp, (int, str)):
        return None, f"page fetch failed: {page_resp} ({page_url})"

    page_text = page_resp.text.lower()
    expected = clean_name(expected_name)
    if not expected or expected not in page_text:
        return None, f"expected name {expected_name!r} not found on {page_url}"

    for candidate in (str(n), padded):
        img_url = f"https://www.serebii.net/card/{slug}/{candidate}.jpg"
        img_resp = try_get(img_url)
        if not isinstance(img_resp, (int, str)):
            return img_resp.content, None

    return None, f"image fetch failed (both number formats) at {page_url}"


# --- Phase 1: read every set's products up front, then drop the DB connection ---
sets_data = []
for code, slug in SET_SLUGS.items():
    try:
        cs = CardSet.objects.get(code=code)
    except CardSet.DoesNotExist:
        print(f"=== {code}: no such CardSet in DB, skipping ===")
        continue
    products = list(PokemonProduct.objects.filter(card_set=cs, is_active=True).values('id', 'name', 'card_number'))
    sets_data.append((code, slug, cs.name, products))

connection.close()
total_products = sum(len(s[3]) for s in sets_data)
print(f"Loaded {total_products} products across {len(sets_data)} sets. Connection closed -- starting Serebii fetches.\n")

grand_updated = 0
grand_broken = []

for code, slug, cs_name, products in sets_data:
    print(f"=== {code} ({cs_name}) -> serebii slug '{slug}' -- {len(products)} active products ===")

    verified = []
    set_broken = []
    fetchable = [p for p in products if p['card_number']]
    for p in products:
        if not p['card_number']:
            set_broken.append((p, "no card_number -- not a numbered card, skipping"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(verify_and_fetch, slug, p['card_number'], p['name']): p for p in fetchable}
        for fut in as_completed(futures):
            p = futures[fut]
            img_bytes, err = fut.result()
            if err:
                set_broken.append((p, err))
                continue
            print(f"  VERIFIED id={p['id']} #{p['card_number']} {p['name']!r} ({len(img_bytes)} bytes)")
            verified.append((p, img_bytes))

    print(f"  -> {len(verified)} verified, {len(set_broken)} broken/skipped")
    if set_broken:
        print(f"     sample broken reasons:")
        for p, reason in set_broken[:5]:
            print(f"       id={p['id']} {p['name']!r}: {reason}")
    print()

    if not DRY_RUN and verified:
        connection.close()
        to_update = []
        for p, img_bytes in verified:
            key = f"cards/{code}/{code}_{str(p['card_number']).zfill(3)}_serebii.jpg"
            s3.put_object(Bucket=R2_BUCKET, Key=key, Body=img_bytes, ContentType="image/jpeg")
            new_url = f"{PUBLIC_URL}/{key}"
            obj = PokemonProduct(id=p['id'], image_url=new_url, image_small_url=new_url)
            to_update.append(obj)
        PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=50)
        grand_updated += len(to_update)
        connection.close()

    grand_broken.extend([(code, p, reason) for p, reason in set_broken])

print("=" * 70)
if DRY_RUN:
    print("DRY RUN — nothing written. Review the VERIFIED/broken output above, then set DRY_RUN = False and rerun.")
else:
    print(f"TOTAL updated across all SWSH sets: {grand_updated}")

print(f"\n--- ALL broken/skipped across all sets ({len(grand_broken)}) ---")
for code, p, reason in grand_broken:
    print(f"  [{code}] id={p['id']} {p['name']!r}: {reason}")
