# PokeBulk SA - Download Images To R2
# v1.0 (patched: card_rows now also filters by --set-code, not just is_card)
#
# Takes a bible-format sheet (post Bulbapedia enrichment, e.g.
# PBL_bible_format_check_expanded_bulba_enriched.csv) and, for each card row:
#   1. Picks the best available source image: bulba_image_url first,
#      falling back to tcgplayer_image_url if Bulbapedia didn't match.
#   2. Downloads it (with browser-style headers, same as fix_ccc_images.py).
#   3. Uploads it to R2 at cards/{set_code}/{product_id}_{variant_code}.jpg
#   4. Updates final_image_url (and final_image_source) to the new R2 URL.
#
# Sealed products (is_card != True) are skipped entirely.
# Rows with no image URL at all (e.g. synthesized RH placeholders that
# didn't get matched during enrichment) are skipped and reported, not guessed.
#
# BUG FIX (2026-07-13): card_rows previously only filtered on is_card=='true',
# so --set-code only controlled where files were WRITTEN (the R2 folder path),
# not which rows got PROCESSED -- running this against a full multi-set bible
# CSV would silently process every card in the file, not just the given set.
# Confirmed via dry-run against pokebulk_bible_v7.csv --set-code PBL: reported
# "Would update: 36047" instead of the expected ~188 PBL rows. Now filters on
# both is_card AND set_code together.
#
# Credentials are read from environment variables -- nothing sensitive is
# hardcoded here. Set these in PowerShell before running:
#
#   $env:R2_ACCOUNT_ID = "your-cloudflare-account-id"
#   $env:R2_ACCESS_KEY_ID = "your-r2-access-key-id"
#   $env:R2_SECRET_ACCESS_KEY = "your-r2-secret-access-key"
#
# Save to: C:\Users\texca\pokemart-api\download_images_to_r2_v1.0.py
#
# Usage:
#   python download_images_to_r2_v1.0.py --in PBL_bible_format_check_expanded_bulba_enriched.csv --set-code PBL
#   python download_images_to_r2_v1.0.py --in ... --set-code PBL --dry-run
#   python download_images_to_r2_v1.0.py --in ... --set-code PBL --limit 10   # quick test batch

import csv
import os
import sys
import time
import hashlib
import argparse
import requests
import boto3
from botocore.config import Config

R2_BUCKET = 'pokebulkcards'
PUBLIC_URL = 'https://images.pokebulk.co.za'
DELAY_SECS = 0.15

# Bulbapedia/Wikimedia actively blocks generic browser-impersonation UAs --
# identify honestly instead, same as enrich_bulbapedia.py (which already
# works against archives.bulbagarden.net).
BULBA_HEADERS = {
    'User-Agent': 'PokeBulkSA/1.0.0 (enquiries@pokebulk.co.za)',
}

# TCGplayer CDN wants a browser-style UA + a tcgplayer.com referer to get
# past its own hotlink protection -- same header set as fix_ccc_images.py.
TCGPLAYER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
    'Referer': 'https://www.tcgplayer.com/',
}


def get_r2_client():
    account_id = os.environ.get('R2_ACCOUNT_ID')
    access_key = os.environ.get('R2_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')

    missing = [n for n, v in [('R2_ACCOUNT_ID', account_id),
                               ('R2_ACCESS_KEY_ID', access_key),
                               ('R2_SECRET_ACCESS_KEY', secret_key)] if not v]
    if missing:
        print('Missing required environment variable(s): ' + ', '.join(missing))
        sys.exit(1)

    endpoint_url = 'https://' + account_id + '.r2.cloudflarestorage.com'
    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


def try_download(url, source_label):
    headers = BULBA_HEADERS if source_label == 'bulbapedia' else TCGPLAYER_HEADERS
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code == 200 and resp.content:
            return resp
        if resp.status_code == 404 and source_label == 'bulbapedia' and 'AbyssEye' in url:
            # Bulbapedia has been renaming Pitch Black files from their Japanese
            # source name to the English one as real scans land (confirmed via
            # File:TropiusPitchBlack1.jpg's history, 2026-07-13 -- same card
            # number, filename swaps "AbyssEye" for "PitchBlack"). BUT the old
            # URL's a/ab directory prefix is a hash of the OLD filename -- it's
            # wrong for the new filename and can't just be reused. MediaWiki
            # shards files into media/upload/{h[0]}/{h[0:2]}/{filename} where
            # h = md5(filename). Recompute it for the new filename instead of
            # blindly substituting into the old URL. Verified against real
            # paths 2026-07-13: TropiusPitchBlack1.jpg -> 4/4b (matches live),
            # FomantisPitchBlack3.jpg -> c/c5 (matches live), LurantisexPitchBlack4.jpg -> 9/96 (matches live).
            old_filename = url.rsplit('/', 1)[-1]
            new_filename = old_filename.replace('AbyssEye', 'PitchBlack')
            file_hash = hashlib.md5(new_filename.encode('utf-8')).hexdigest()
            retry_url = (
                'https://archives.bulbagarden.net/media/upload/'
                + file_hash[0] + '/' + file_hash[0:2] + '/' + new_filename
            )
            retry_resp = requests.get(retry_url, timeout=15, headers=headers)
            if retry_resp.status_code == 200 and retry_resp.content:
                return retry_resp
            return 'HTTP 404 (also tried PitchBlack rename at ' + retry_url + ': HTTP ' + str(retry_resp.status_code) + ')'
        return 'HTTP ' + str(resp.status_code)
    except Exception as e:
        return str(e)


def safe_filename(product_id, variant_code):
    pid = ''.join(c if c.isalnum() else '_' for c in str(product_id))
    code = ''.join(c if c.isalnum() else '_' for c in str(variant_code or 'N'))
    return pid + '_' + code + '.jpg'


def main():
    parser = argparse.ArgumentParser(description='PokeBulk SA - Download Images To R2 v1.0')
    parser.add_argument('--in', dest='in_path', required=True, help='Bible-format CSV (post Bulbapedia enrichment)')
    parser.add_argument('--set-code', required=True, help='Set code -- filters which rows are processed AND sets the R2 folder (cards/{set_code}/...)')
    parser.add_argument('--out', dest='out_path', default=None, help='Output CSV path (default: <input>_r2.csv)')
    parser.add_argument('--dry-run', action='store_true', help='Print the plan, download nothing, upload nothing')
    parser.add_argument('--limit', type=int, default=None, help='Only process the first N card rows (for a quick test)')
    args = parser.parse_args()

    if not os.path.isfile(args.in_path):
        print('ERROR: input file not found: ' + args.in_path)
        return

    out_path = args.out_path or (os.path.splitext(args.in_path)[0] + '_r2.csv')

    with open(args.in_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)

    print('Read ' + str(len(rows)) + ' row(s) from ' + args.in_path)

    # BUG FIX: also filter by set_code -- previously only is_card was checked,
    # so running this against a full multi-set bible CSV silently processed
    # every card in the file instead of just the requested set.
    card_rows = [
        r for r in rows
        if r.get('is_card', '').strip().lower() == 'true'
        and r.get('set_code', '').strip() == args.set_code
    ]
    if args.limit:
        # Keep all non-card rows untouched, only cap how many CARD rows get processed
        card_ids = set(id(r) for r in card_rows[:args.limit])
        process_rows = [r for r in card_rows if id(r) in card_ids]
    else:
        process_rows = card_rows

    print('Card rows matching set_code=' + args.set_code + ': ' + str(len(card_rows)) + '  |  Will process: ' + str(len(process_rows)))

    if not args.dry_run:
        s3 = get_r2_client()
    else:
        s3 = None

    updated = 0
    skipped_no_source = 0
    failed = []

    for i, row in enumerate(process_rows, 1):
        product_id = row.get('product_id', '').strip()
        variant_code = row.get('variant_code', '').strip()
        name = row.get('name', '')

        source_url = row.get('bulba_image_url', '').strip() or row.get('tcgplayer_image_url', '').strip()
        if not source_url:
            skipped_no_source += 1
            continue

        source_label = 'bulbapedia' if row.get('bulba_image_url', '').strip() else 'tcgplayer'

        if i % 25 == 0 or i == len(process_rows):
            print('  [' + str(i) + '/' + str(len(process_rows)) + '] ' + name)

        if args.dry_run:
            print('  [DRY] ' + str(product_id) + ' ' + str(variant_code) + ' ' + name + '  <- ' + source_label + ': ' + source_url)
            updated += 1
            continue

        result = try_download(source_url, source_label)
        if isinstance(result, str):
            failed.append((product_id, name, source_label, result))
            continue

        key = 'cards/' + args.set_code + '/' + safe_filename(product_id, variant_code)
        content_type = result.headers.get('Content-Type', 'image/jpeg')
        try:
            s3.put_object(Bucket=R2_BUCKET, Key=key, Body=result.content, ContentType=content_type)
        except Exception as e:
            failed.append((product_id, name, source_label, 'R2 upload failed: ' + str(e)))
            continue

        new_url = PUBLIC_URL + '/' + key
        row['final_image_url'] = new_url
        row['final_image_source'] = 'r2_' + source_label
        updated += 1
        time.sleep(DELAY_SECS)

    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print('\n' + '=' * 60)
    print('Done!')
    print('  ' + ('Would update' if args.dry_run else 'Updated') + ': ' + str(updated))
    print('  Skipped (no image URL at all): ' + str(skipped_no_source))
    print('  Failed downloads/uploads: ' + str(len(failed)))
    print('  Saved to: ' + out_path)
    if failed:
        print('\n  Failed rows:')
        for pid, name, label, reason in failed:
            print('    ' + str(pid) + ' | ' + name + ' | source=' + label + ' | ' + reason)
    if skipped_no_source:
        print('\n  NOTE: a row with no image URL at all is unusual after Bulbapedia')
        print('  enrichment, since enrich_bulbapedia.py caches by (name, set_code, number)')
        print('  -- synthesized RH rows share that cache key with their base row and should')
        print('  already have inherited the same bulba_image_url. Worth checking these')
        print('  specific rows by hand rather than assuming it is expected.')
    print('=' * 60)


if __name__ == '__main__':
    main()
