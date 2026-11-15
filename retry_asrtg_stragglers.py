import django, os, re, time
import requests
import boto3
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct

# 8 ASRTG products failed on the first fix_tg_gallery_images.py apply run --
# all clustered H7-H13 with one explicit "Read timed out" in the middle,
# right after all 30 BRSTG cards + the first 6 ASRTG cards had already
# fetched cleanly. Looks like a plain network blip during that window, not
# a real Serebii-side issue (unlike BS2/LC, which failed the exact same way
# even in an isolated, slow, low-concurrency retry). Retrying just these 8,
# sequentially, with generous timeouts.

DRY_RUN = False  # review, then set False and rerun

SLUG = 'astralradiance'
IDS = [403978, 403979, 403980, 403981, 403982, 403983, 403984, 403975]

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


def clean_name(name):
    name = (name or '').strip()
    prev = None
    while prev != name:
        prev = name
        name = TRAIL_BRACKET.sub('', name)
        name = TRAIL_PAREN.sub('', name)
        name = TRAIL_SETNUM.sub('', name)
        name = TRAIL_SLASHCODE.sub('', name)
        name = TRAIL_DASHCODE.sub('', name)
    return re.sub(r'\s+', ' ', name).strip().lower()


def try_get(url, retries=5, timeout=30):
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
            time.sleep(4 * (attempt + 1))
    return last_err


products = list(PokemonProduct.objects.filter(id__in=IDS).values('id', 'name', 'card_number'))
connection.close()
print(f"Retrying {len(products)} products.\n")

verified = []
broken = []
for p in products:
    n = int(p['card_number'])
    page_url = f"https://www.serebii.net/card/{SLUG}/H{n}.shtml"
    page_resp = try_get(page_url)
    if isinstance(page_resp, (int, str)):
        broken.append((p, f"page fetch failed: {page_resp}"))
        continue
    expected = clean_name(p['name'])
    if not expected or expected not in page_resp.text.lower():
        broken.append((p, f"name {p['name']!r} not found on {page_url}"))
        continue
    img_url = f"https://www.serebii.net/card/{SLUG}/h{n}.jpg"
    img_resp = try_get(img_url)
    if isinstance(img_resp, (int, str)):
        broken.append((p, f"image fetch failed: {img_resp}"))
        continue
    print(f"  VERIFIED id={p['id']} H{n} {p['name']!r} ({len(img_resp.content)} bytes)")
    verified.append((p, n, img_resp.content))
    time.sleep(1)

print(f"\n-> {len(verified)} verified, {len(broken)} still broken")
for p, reason in broken:
    print(f"   id={p['id']} {p['name']!r}: {reason}")

if not DRY_RUN and verified:
    connection.close()
    to_update = []
    for p, n, img_bytes in verified:
        key = f"cards/ASRTG/ASRTG_H{n}_serebii.jpg"
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=img_bytes, ContentType="image/jpeg")
        new_url = f"{PUBLIC_URL}/{key}"
        obj = PokemonProduct(id=p['id'], image_url=new_url, image_small_url=new_url)
        to_update.append(obj)
    PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=10)
    print(f"\nUpdated {len(to_update)} products.")
elif DRY_RUN:
    print("\nDRY RUN — nothing written. Set DRY_RUN = False and rerun to apply.")
