"""
set_symbol_from_bulba.py -- PokeBulk SA
Resolves an archives.bulbagarden.net file page ID (or a direct image URL), downloads the image, uploads it to
R2 (rule: images always on R2) and sets CardSet.symbol_url (or logo_url with --kind logo).

  python set_symbol_from_bulba.py --set-code DLR --pageid 434276 --dry-run
  python set_symbol_from_bulba.py --set-code DLR --pageid 434276
  python set_symbol_from_bulba.py --set-code DLR --pageid 434276 --kind logo
  python set_symbol_from_bulba.py --set-code DLR --url https://.../file.png
R2 keys: sets/symbols/{code}_symbol.png   |   sets/logos/{code}_logo.png
"""
import argparse
import mimetypes
import os
import sys

import requests

UA = "PokeBulkSA/1.0.0 (enquiries@pokebulk.co.za)"
API = "https://archives.bulbagarden.net/w/api.php"


def resolve(pageid):
    r = requests.get(API, params={'action': 'query', 'pageids': pageid, 'prop': 'imageinfo',
                                  'iiprop': 'url|size|mime', 'format': 'json'},
                     headers={'User-Agent': UA}, timeout=30)
    r.raise_for_status()
    page = list(r.json()['query']['pages'].values())[0]
    info = (page.get('imageinfo') or [None])[0]
    if not info:
        sys.exit(f'No image found for page id {pageid} (title: {page.get("title")})')
    print(f"Found: {page.get('title')}  {info.get('width')}x{info.get('height')}  {info.get('mime')}")
    return info['url']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set-code', required=True)
    ap.add_argument('--pageid')
    ap.add_argument('--url')
    ap.add_argument('--kind', choices=['symbol', 'logo'], default='symbol')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not (a.pageid or a.url):
        sys.exit('Give --pageid or --url')

    src = a.url or resolve(a.pageid)
    print('Source:', src)
    img = requests.get(src, headers={'User-Agent': UA}, timeout=60)
    img.raise_for_status()
    ctype = img.headers.get('content-type') or mimetypes.guess_type(src)[0] or 'image/png'
    ext = 'png' if 'png' in ctype else ('jpg' if 'jpeg' in ctype or 'jpg' in ctype else 'png')
    key = f"sets/{'symbols' if a.kind == 'symbol' else 'logos'}/{a.set_code}_{a.kind}.{ext}"
    cdn_url = f"https://images.pokebulk.co.za/{key}"
    print(f'{len(img.content)} bytes, {ctype} -> R2 key {key}')

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from products.models import CardSet
    cs = CardSet.objects.filter(code=a.set_code).first()
    if not cs:
        sys.exit(f'CardSet {a.set_code} not found')
    field = 'symbol_url' if a.kind == 'symbol' else 'logo_url'
    print(f'{a.set_code}.{field}: {getattr(cs, field)!r} -> {cdn_url}')
    if a.dry_run:
        print('Dry run only.')
        return

    from products.admin import _r2_client, R2_BUCKET
    _r2_client().put_object(Bucket=R2_BUCKET, Key=key, Body=img.content, ContentType=ctype)
    setattr(cs, field, cdn_url)
    cs.save(update_fields=[field])
    print('Done.')


if __name__ == '__main__':
    main()
