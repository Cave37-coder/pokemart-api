"""
upload_full_images.py - PokeBulk SA

Replace a set's card images with full-size ones, hosted on R2 (never an
external hotlink -- see CLAUDE.md "Image hosting").  Michael, 2026-10-09:
"try download new full size images for 30th".

For each distinct TCGplayer product in the set it tries, in order:
  1. TCGplayer CDN   https://tcgplayer-cdn.tcgplayer.com/product/<pid>_in_1000x1000.jpg
  2. Serebii         https://www.serebii.net/card/<slug>/<card_number>.jpg   (only if --serebii-slug)
keeps the first one that downloads, is a real JPEG/PNG, and is at least
--min-width pixels wide (default 500, i.e. clearly bigger than the old
200px TCGCSV thumbnails), uploads it to R2 as  cards/<set>_<pid>_hq.jpg  and
points EVERY variant row of that product (image_url + image_small_url) at it.
The old image is untouched in R2 until you decide to delete it, and the new
key is different, so there is no stale-CDN-cache problem and rollback is just
re-running the old URLs.

  python manage.py upload_full_images --set 30C --dry-run     # report only, 3 cards
  python manage.py upload_full_images --set 30C --dry-run --limit 0   # report all
  python manage.py upload_full_images --set 30C --serebii-slug 30thcelebration
  python manage.py upload_full_images --set 30C --force       # redo already-hq rows
"""
import io
import time

import requests
from django.core.management.base import BaseCommand

from products.models import PokemonProduct
from products.admin import _r2_client, R2_BUCKET, R2_CDN   # reuse the established R2 credentials

try:
    from PIL import Image
except Exception:  # Pillow optional -- fall back to a size heuristic
    Image = None

UA = {"User-Agent": "Mozilla/5.0 (compatible; PokeBulkSA-ImageSync/1.0; +https://pokebulk.co.za)"}


def candidate_urls(pid, number, serebii_slug):
    urls = []
    if pid:
        urls.append(f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_in_1000x1000.jpg")
    if serebii_slug and number:
        urls.append(f"https://www.serebii.net/card/{serebii_slug}/{int(number)}.jpg")
    return urls


def measure(content):
    """(width, height) or None when it isn't a decodable image."""
    if Image is None:
        return (999, 999) if len(content) > 30000 else None
    try:
        im = Image.open(io.BytesIO(content))
        return im.size
    except Exception:
        return None


def fetch_best(urls, min_width):
    for u in urls:
        try:
            r = requests.get(u, headers=UA, timeout=25)
        except requests.RequestException as e:
            yield u, None, f"error {e.__class__.__name__}"
            continue
        if r.status_code != 200:
            yield u, None, f"HTTP {r.status_code}"
            continue
        size = measure(r.content)
        if not size:
            yield u, None, "not a valid image"
            continue
        if size[0] < min_width:
            yield u, None, f"too small {size[0]}x{size[1]}"
            continue
        yield u, (r.content, size, r.headers.get("Content-Type", "image/jpeg")), "ok"
        return


class Command(BaseCommand):
    help = "Download full-size card images for a set and re-host them on R2."

    def add_arguments(self, parser):
        parser.add_argument("--set", dest="set_code", default="30C")
        parser.add_argument("--serebii-slug", default="", help="e.g. 30thcelebration (fallback source)")
        parser.add_argument("--min-width", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=3, help="With --dry-run: cards to test (0 = all). Ignored otherwise.")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--delay", type=float, default=0.4)

    def handle(self, *args, **o):
        code = o["set_code"].upper()
        rows = list(PokemonProduct.objects.filter(card_set__code=code, tcgcsv_product_id__isnull=False)
                    .order_by("card_number", "variant_sort"))
        by_pid = {}
        for p in rows:
            by_pid.setdefault(p.tcgcsv_product_id, []).append(p)
        pids = list(by_pid)
        self.stdout.write(f"[{code}] {len(rows)} rows, {len(pids)} distinct TCGplayer products")

        if o["dry_run"] and o["limit"]:
            pids = pids[: o["limit"]]

        s3 = None if o["dry_run"] else _r2_client()
        ok = skipped = failed = 0
        for i, pid in enumerate(pids, 1):
            group = by_pid[pid]
            first = group[0]
            if not o["force"] and all("_hq." in (p.image_url or "") for p in group):
                skipped += 1
                continue
            urls = candidate_urls(pid, first.card_number, o["serebii_slug"])
            result = None
            for url, payload, status in fetch_best(urls, o["min_width"]):
                self.stdout.write(f"  #{first.card_number} {first.name[:28]:28} {status:>22}  {url}")
                if payload:
                    result = payload
                    break
            time.sleep(o["delay"])
            if not result:
                failed += 1
                continue
            content, size, ctype = result
            key = f"cards/{code.lower()}_{pid}_hq.jpg"
            if o["dry_run"]:
                self.stdout.write(f"    -> would upload {size[0]}x{size[1]} ({len(content)//1024} KB) to {R2_CDN}/{key} "
                                  f"for {len(group)} variant row(s)")
                ok += 1
                continue
            s3.put_object(Bucket=R2_BUCKET, Key=key, Body=content, ContentType="image/jpeg",
                          CacheControl="public, max-age=31536000")
            url = f"{R2_CDN}/{key}"
            for p in group:
                p.image_url = url
                p.image_small_url = url
            PokemonProduct.objects.bulk_update(group, ["image_url", "image_small_url"])
            ok += 1
            if i % 25 == 0:
                self.stdout.write(f"  ... {i}/{len(pids)}")

        self.stdout.write(f"\nDONE  uploaded/ok: {ok}  already hq: {skipped}  no usable image: {failed}"
                          + ("  (DRY RUN - nothing uploaded)" if o["dry_run"] else ""))
