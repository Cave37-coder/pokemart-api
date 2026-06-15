import django, os, time, requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import boto3
from botocore.config import Config
from products.models import PokemonProduct
from django.db import connection

ACCOUNT_ID  = '229506129ad4206787dd4d3227608e17'
ACCESS_KEY  = 'f78ec2aa11639bd6a34e38d6315bcfbd'
SECRET_KEY  = 'ba88661966102498e0e6df428047dbf13bbafda45f4c33bb7284f138da386c11'
BUCKET      = 'pokebulkcards'
PUBLIC_URL  = 'https://pub-77a8c30ac1fc4f4fbe1f2a7a0f15f174.r2.dev'
ENDPOINT    = f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com'

s3 = boto3.client(
    's3',
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

def make_key(product):
    set_code = (product.card_set.code if product.card_set else 'unknown').lower()
    pid = product.tcgcsv_product_id or product.id
    variant = (product.variant_override or 'n').lower()
    ext = 'jpg'
    if product.image_url and '.png' in product.image_url:
        ext = 'png'
    return f'cards/{set_code}_{pid}_{variant}.{ext}'

uploaded = 0
failed = 0
skipped = 0
to_update = []

qs = PokemonProduct.objects.select_related('card_set').exclude(image_url='').exclude(image_url__contains='r2.dev')
total = qs.count()
print(f'Total to process: {total}')

for i, product in enumerate(qs.iterator(), 1):
    if i % 500 == 0:
        print(f'Progress: {i}/{total} | Uploaded:{uploaded} Failed:{failed} Skipped:{skipped}')

    key = make_key(product)
    try:
        img_resp = requests.get(product.image_url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if img_resp.status_code != 200:
            failed += 1
            if failed <= 10:
                print(f'  HTTP {img_resp.status_code}: {product.image_url[:60]}')
            continue
        content_type = 'image/png' if '.png' in product.image_url else 'image/jpeg'
        s3.put_object(Bucket=BUCKET, Key=key, Body=img_resp.content, ContentType=content_type)
        new_url = f'{PUBLIC_URL}/{key}'
        product.image_url = new_url
        product.image_small_url = new_url
        to_update.append(product)
        uploaded += 1
    except Exception as e:
        failed += 1
        if failed <= 10:
            print(f'  FAILED: {product.name[:30]} | {e}')
        time.sleep(0.5)
        continue

    if len(to_update) >= 50:
        try:
            connection.ensure_connection()
            PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=200)
            print(f'  Saved {len(to_update)} records...')
            to_update = []
        except Exception as e:
            connection.close()
            time.sleep(2)

if to_update:
    PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=200)

print(f'DONE | Uploaded:{uploaded} Failed:{failed} Skipped:{skipped}')
