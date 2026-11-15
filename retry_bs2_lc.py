import django, os, re, time
import requests
import boto3
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct, CardSet

# BS2 (Base Set 2) and LC (Legendary Collection) came back 0% verified in the
# full fix_classic_era_images.py dry run -- every card failed, mixing both
# "name not found on page" AND "image fetch failed (both number formats)"
# uniformly across the whole set. That's a different failure signature than
# the two real URL-scheme bugs found earlier this session (Shining Fates
# Shiny Vault, Aquapolis/Skyridge Holo Rares), which failed with clean 404s
# on specific known-wrong URLs.
#
# Direct fetch of serebii.net/card/baseset2/004.shtml and .../legendary/003.shtml
# confirms BOTH the page URL scheme AND the image URL scheme
# ({slug}/{number}.jpg, unpadded, no zero-fill) are exactly what the main
# script already tries first -- so this isn't a slug/numbering bug. BS2 and
# LC were the 3rd and 10th sets processed in a long sequential run, right
# after the two largest sets (AQ=178 groups, JU+G1+G2 combined). The uniform
# whole-set failure pattern -- not scattered individual misses -- points at
# transient rate-limiting/blocking during those specific windows rather than
# a structural problem.
#
# This script re-runs ONLY those two sets, isolated, with lower concurrency
# and a Referer header (Serebii sometimes hotlink-protects card images), to
# check whether it was a one-off. Same verify-before-trust methodology as
# every other script this session: a card's image is never written unless
# its Serebii page independently contains the expected name first.

DRY_RUN = True  # review, then set False and rerun

SET_SLUGS = {
    'BS2': 'baseset2',
    'LC':  'legendary',
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
HOLO_RARE_SUFFIX = re.compile(r'\s*\(H(\d+)\)\s*$', re.IGNORECASE)


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


def parse_variant(product):
    name = product['name'] or ''
    m = HOLO_RARE_SUFFIX.search(name)
    if m:
        return True, int(m.group(1)), HOLO_RARE_SUFFIX.sub('', name).strip()
    return False, int(product['card_number']), name


def try_get(url, retries=4, timeout=25, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
            last_err = resp.status_code
            if last_err == 404:
                return last_err
        except Exception as e:
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
    return last_err


def verify_and_fetch_group(slug, is_holo_rare, number, candidate_names):
    padded = str(number).zfill(3)
    page_url = f"https://www.serebii.net/card/{slug}/{padded}.shtml"
    page_resp = try_get(page_url)
    if isinstance(page_resp, (int, str)):
        return None, f"page fetch failed: {page_resp} ({page_url})"
    page_text = page_resp.text.lower()
    matched = any(clean_name(n) and clean_name(n) in page_text for n in candidate_names)
    if not matched:
        return None, f"none of {candidate_names!r} found on {page_url}"
    for candidate in (str(number), padded):
        img_url = f"https://www.serebii.net/card/{slug}/{candidate}.jpg"
        img_resp = try_get(img_url, referer=page_url)
        if not isinstance(img_resp, (int, str)):
            return img_resp.content, None
    return None, f"image fetch failed (both number formats) at {page_url}"


sets_data = []
for code, slug in SET_SLUGS.items():
    cs = CardSet.objects.get(code=code)
    products = list(PokemonProduct.objects.filter(card_set=cs, is_active=True).values('id', 'name', 'card_number'))
    sets_data.append((code, slug, cs.name, products))

connection.close()
print(f"Loaded {sum(len(s[3]) for s in sets_data)} products across {len(sets_data)} sets. Connection closed.\n")

grand_updated = 0
grand_broken = []

for code, slug, cs_name, products in sets_data:
    groups = defaultdict(list)
    skipped = []
    for p in products:
        if not p['card_number'] and not HOLO_RARE_SUFFIX.search(p['name'] or ''):
            skipped.append((p, "no card_number -- not a numbered card, skipping"))
            continue
        key = parse_variant(p)[:2]
        groups[key].append(p)

    print(f"=== {code} ({cs_name}) -> serebii slug '{slug}' -- {len(products)} active products, {len(groups)} unique cards to fetch ===")

    verified_groups = []
    broken_groups = []

    def work(item):
        key, members = item
        is_holo_rare, number = key
        names = [parse_variant(m)[2] for m in members]
        img_bytes, err = verify_and_fetch_group(slug, is_holo_rare, number, names)
        return key, members, img_bytes, err

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(work, item): item for item in groups.items()}
        for fut in as_completed(futures):
            key, members, img_bytes, err = fut.result()
            label = f"H{key[1]}" if key[0] else str(key[1]).zfill(3)
            if err:
                broken_groups.append((key, members, err))
                continue
            names = ', '.join(sorted({m['name'] for m in members}))
            print(f"  VERIFIED #{label} {names!r} -> {len(members)} product(s) ({len(img_bytes)} bytes)")
            verified_groups.append((key, members, img_bytes))

    total_verified_products = sum(len(m) for _, m, _ in verified_groups)
    total_broken_products = sum(len(m) for _, m, _ in broken_groups) + len(skipped)
    print(f"  -> {len(verified_groups)} cards verified ({total_verified_products} products), {len(broken_groups)} cards broken ({total_broken_products} products incl. skipped)")
    if broken_groups or skipped:
        print(f"     broken reasons:")
        for key, members, reason in broken_groups[:15]:
            label = f"H{key[1]}" if key[0] else str(key[1]).zfill(3)
            print(f"       #{label} {[m['name'] for m in members]}: {reason}")
        for p, reason in skipped[:15]:
            print(f"       id={p['id']} {p['name']!r}: {reason}")
    print()

    if not DRY_RUN and verified_groups:
        connection.close()
        to_update = []
        for key, members, img_bytes in verified_groups:
            is_holo_rare, number = key
            key_number = f"H{number}" if is_holo_rare else str(number).zfill(3)
            r2_key = f"cards/{code}/{code}_{key_number}_serebii.jpg"
            s3.put_object(Bucket=R2_BUCKET, Key=r2_key, Body=img_bytes, ContentType="image/jpeg")
            new_url = f"{PUBLIC_URL}/{r2_key}"
            for p in members:
                obj = PokemonProduct(id=p['id'], image_url=new_url, image_small_url=new_url)
                to_update.append(obj)
        PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=50)
        grand_updated += len(to_update)
        connection.close()

    for key, members, reason in broken_groups:
        for p in members:
            grand_broken.append((code, p, reason))
    for p, reason in skipped:
        grand_broken.append((code, p, reason))

print("=" * 70)
if DRY_RUN:
    print("DRY RUN — nothing written. Review the VERIFIED/broken output above, then set DRY_RUN = False and rerun.")
else:
    print(f"TOTAL products updated: {grand_updated}")

print(f"\n--- ALL broken/skipped ({len(grand_broken)}) ---")
for code, p, reason in grand_broken:
    print(f"  [{code}] id={p['id']} {p['name']!r}: {reason}")
