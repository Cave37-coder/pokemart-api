import django, os, re, time
import requests
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

# Michael, 2026-08-04: "No all promo cards, all!!!" -- extends the verified
# Serebii re-source used for Celebrations (2026-08-02) and SV Promos to
# EVERY promo set in the catalog. Slugs below confirmed by actually reading
# Serebii's "English Promos" index page (serebii.net/card/engpromo.shtml),
# not guessed.
#
# Same non-negotiable safety net as every prior image-fix script this
# session: a card's image is NEVER trusted just because a URL returns 200 --
# its Serebii page must actually CONTAIN the expected Pokemon/card name
# first. A wrong slug/numbering mismatch shows up as "still_broken" for
# that whole set, it can never silently apply the wrong art.
#
# FIX vs. the first run: that one crashed with "server closed the
# connection unexpectedly" partway through PR-SM -- Railway's DB proxy
# kills an idle connection, and this script holds one open the whole time
# while doing hundreds of slow Serebii HTTP calls with barely any DB
# activity in between. Fix: read each set's products into plain Python
# objects, then explicitly connection.close() before the slow network
# loop -- Django transparently reopens a fresh connection whenever the
# next query actually happens (next set's read, or the final bulk_update),
# so no connection ever sits idle for minutes.
#
# CCP (Countdown Calendar Promos) has no confirmed match on Serebii's promo
# index and is deliberately EXCLUDED here rather than guessed at.

DRY_RUN = False  # reviewed: 1,425/1,571 verified across all 12 sets -- applying now

SET_SLUGS = {
    'PR-BEST': 'bestofgame',
    'PR-WB':   'wizardspromos',
    'PR-NB':   'nintendopromo',
    'PR-DP':   'dppromo',
    'PR-HS':   'hgsspromo',
    'PR-BLW':  'bwpromos',
    'PR-XY':   'xypromos',
    'PR-SM':   'smpromos',
    'MEP':     'megapromos',
    'SMP':     'smpromos',
    'SVP':     'svpromos',
    'PR-SWSH': 'swshpromos',
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

# Same iterative decoration-stripper proven out earlier this session on the
# pokedex_number backfill matcher -- promo card names in this catalog stack
# MULTIPLE trailing decorations ("Mothim - 42/100 (Prerelease)", "Champions
# Festival - BW95 (Worlds 13) [Top Thirty-Two]") that Serebii's own page
# text never shows. The first version of this script only stripped one
# trailing (...) group, which is why sets like PR-NB/PR-DP/PR-HS/PR-BLW came
# back near-0% even though the slug and page were correct -- it was a
# string-matching bug in THIS script, not a wrong Serebii set.
TRAIL_BRACKET = re.compile(r'\s*\[[^\]]*\]\s*$')
TRAIL_PAREN = re.compile(r'\s*\([^)]*\)\s*$')
TRAIL_SETNUM = re.compile(r'\s*-\s*\d+/\d+\s*$')
TRAIL_SLASHCODE = re.compile(r'\s*-\s*\d+/[A-Za-z0-9-]+\s*$')
TRAIL_DASHCODE = re.compile(r'\s*-\s*[A-Za-z]{0,6}\d+[A-Za-z]{0,2}\s*$')  # " - BW54", " - SM64", " - 8", " - DP01"


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


def verify_and_fetch(slug, card_number, expected_name):
    padded = str(int(card_number)).zfill(3)
    page_url = f"https://www.serebii.net/card/{slug}/{padded}.shtml"
    page_resp = try_get(page_url)
    if isinstance(page_resp, (int, str)):
        return None, f"page fetch failed: {page_resp} ({page_url})"

    page_text = page_resp.text.lower()
    expected = clean_name(expected_name)
    if not expected or expected not in page_text:
        return None, f"expected name {expected_name!r} not found on {page_url}"

    for candidate in (str(int(card_number)), padded):
        img_url = f"https://www.serebii.net/card/{slug}/{candidate}.jpg"
        img_resp = try_get(img_url)
        if not isinstance(img_resp, (int, str)):
            return img_resp.content, None

    return None, f"image fetch failed (both number formats) at {page_url}"


# --- Phase 1: read every set's products up front, then drop the DB connection ---
sets_data = []  # [(code, slug, cardset_name, [products])]
for code, slug in SET_SLUGS.items():
    try:
        cs = CardSet.objects.get(code=code)
    except CardSet.DoesNotExist:
        print(f"=== {code}: no such CardSet in DB, skipping ===")
        continue
    products = list(PokemonProduct.objects.filter(card_set=cs, is_active=True).values('id', 'name', 'card_number'))
    sets_data.append((code, slug, cs.name, products))

connection.close()  # nothing DB-related happens again until bulk_update below
print(f"Loaded {sum(len(s[3]) for s in sets_data)} products across {len(sets_data)} sets. Connection closed -- starting Serebii fetches.\n")

grand_updated = 0
grand_broken = []

for code, slug, cs_name, products in sets_data:
    print(f"=== {code} ({cs_name}) -> serebii slug '{slug}' -- {len(products)} active products ===")

    verified = []  # (product_dict, image_bytes)
    set_broken = []
    fetchable = [p for p in products if p['card_number']]
    for p in products:
        if not p['card_number']:
            set_broken.append((p, "no card_number -- not a numbered card, skipping"))

    # Michael, 2026-08-04: "no dry run is taking too long!" -- the slow part
    # is ~1,500 individual Serebii fetches, which is identical work whether
    # DRY_RUN is on or off (the write to R2/DB at the end is fast). Skipping
    # the dry run wouldn't have made this faster, it would've just removed
    # the safety review. What actually helps: fetching several cards at once
    # instead of one at a time. 6 workers is a meaningful speedup (roughly
    # 6x wall-clock) without hammering Serebii -- each individual request
    # still goes through the same retry/backoff and per-card name
    # verification as before, just concurrently.
    with ThreadPoolExecutor(max_workers=6) as pool:
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
        connection.close()  # fresh connection for this set's write, in case it's been a while
        to_update = []
        for p, img_bytes in verified:
            key = f"cards/{code}/{code}_{str(p['card_number']).zfill(3)}_serebii.jpg"
            s3.put_object(Bucket=R2_BUCKET, Key=key, Body=img_bytes, ContentType="image/jpeg")
            new_url = f"{PUBLIC_URL}/{key}"
            obj = PokemonProduct(id=p['id'], image_url=new_url, image_small_url=new_url)
            to_update.append(obj)
        PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=50)
        grand_updated += len(to_update)
        connection.close()  # don't hold it open through the next set's slow fetch loop

    grand_broken.extend([(code, p, reason) for p, reason in set_broken])

print("=" * 70)
if DRY_RUN:
    print("DRY RUN — nothing written. Review the VERIFIED/broken output above, then set DRY_RUN = False and rerun.")
else:
    print(f"TOTAL updated across all promo sets: {grand_updated}")

print(f"\n--- ALL broken/skipped across all sets ({len(grand_broken)}) ---")
for code, p, reason in grand_broken:
    print(f"  [{code}] id={p['id']} {p['name']!r}: {reason}")

print("\nNOTE: CCP (Countdown Calendar Promos) is NOT included -- no confirmed")
print("matching set on Serebii's promo index. Flag separately if you want that")
print("one investigated too.")
