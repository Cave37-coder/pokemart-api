import django, os, re, time
import requests
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

# Michael flagged the Trainer Gallery section as "a disaster" -- confirmed by
# fetching Serebii directly (not guessed): BRSTG/ASRTG/LORTG/SITTG/CRZGG all
# live on Serebii under a completely separate URL scheme from their parent
# set -- H{n}.shtml / h{n}.jpg, capital-H page + lowercase-h image, NO zero
# padding -- e.g. serebii.net/card/brilliantstars/H23.shtml = Umbreon VMAX
# (real card number TG23/TG30), serebii.net/card/crownzenith/H1.shtml =
# Hisuian Voltorb (real card number GG1/GG70). Confirmed the SAME scheme for
# all 5 sets by direct fetch of each one's H1 page before writing this.
#
# fix_swsh_booster_images.py mapped these 5 subsets to their parent slug but
# used the plain zero-padded scheme ({n:03d}.shtml) with no H-prefix case --
# so when it ran for real, every single TG/GG card fetch hit the WRONG page
# (e.g. brilliantstars/023.shtml is Torkoal, not Umbreon VMAX). Pulled the
# full real checklists for both BRS and CRZ and there's zero name overlap
# between the TG/GG list and the parent set's low numbers, so verification
# would have failed clean (not silently swapped in a wrong Pokemon's art) --
# but everything in these 5 subsets is still broken/unfixed either way.
#
# This script re-fetches ALL of them correctly via the H-prefix scheme, same
# verify-before-trust rule as everything else this session: an image is only
# written if the H-page independently contains the expected card name.

DRY_RUN = False  # review VERIFIED/broken output, then set False and rerun

SET_SLUGS = {
    'BRSTG': 'brilliantstars',
    'ASRTG': 'astralradiance',
    'LORTG': 'lostorigin',
    'SITTG': 'silvertempest',
    'CRZGG': 'crownzenith',
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


def verify_and_fetch(slug, n, expected_name):
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
    print(f"=== {code} ({cs_name}) -> serebii slug '{slug}' (H-prefix scheme) -- {len(products)} active products ===")

    verified = []
    set_broken = []
    fetchable = [p for p in products if p['card_number']]
    for p in products:
        if not p['card_number']:
            set_broken.append((p, "no card_number -- can't determine H-number, skipping"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(verify_and_fetch, slug, p['card_number'], p['name']): p for p in fetchable}
        for fut in as_completed(futures):
            p = futures[fut]
            img_bytes, err = fut.result()
            if err:
                set_broken.append((p, err))
                continue
            print(f"  VERIFIED id={p['id']} H{p['card_number']} {p['name']!r} ({len(img_bytes)} bytes)")
            verified.append((p, img_bytes))

    print(f"  -> {len(verified)} verified, {len(set_broken)} broken/skipped")
    if set_broken:
        print(f"     sample broken reasons:")
        for p, reason in set_broken[:8]:
            print(f"       id={p['id']} {p['name']!r}: {reason}")
    print()

    if not DRY_RUN and verified:
        connection.close()
        to_update = []
        for p, img_bytes in verified:
            key = f"cards/{code}/{code}_H{p['card_number']}_serebii.jpg"
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
    print(f"TOTAL products updated across all Trainer Gallery / Galarian Gallery sets: {grand_updated}")

print(f"\n--- ALL broken/skipped across all sets ({len(grand_broken)}) ---")
for code, p, reason in grand_broken:
    print(f"  [{code}] id={p['id']} {p['name']!r}: {reason}")
