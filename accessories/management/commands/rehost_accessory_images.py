"""
Re-host every accessory image that is not yet on R2 (CLAUDE.md "always R2").

Takes, in order: image_source_url, the current external image_url, or the
TCGplayer 200w image for tcgcsv_product_id. Uploads to
accessories/<category>/<sku>.<ext> on the pokebulkcards bucket.

Usage:
    python manage.py rehost_accessory_images --dry-run
    python manage.py rehost_accessory_images
    python manage.py rehost_accessory_images --in-stock-only
"""
import time

from django.core.management.base import BaseCommand

from accessories.models import Accessory
from accessories.r2 import rehost_from_url, is_on_r2, NoSourceImage


class Command(BaseCommand):
    help = "Re-host accessory images on Cloudflare R2."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--in-stock-only", action="store_true", help="Only rows with stock > 0")

    def handle(self, *args, **opts):
        qs = Accessory.objects.all().order_by("id")
        if opts["in_stock_only"]:
            qs = qs.filter(stock__gt=0)
        todo = [a for a in qs if not is_on_r2(a.image_url)]
        self.stdout.write(f"{len(todo)} accessory image(s) not on R2 yet.")
        if opts["dry_run"]:
            for a in todo[:25]:
                self.stdout.write(f"  WOULD re-host {a.sku} {a.name!r} from {a.image_source_url or a.image_url or f'TCGplayer #{a.tcgcsv_product_id}'}")
            self.stdout.write("DRY RUN -- nothing written.")
            return
        done = skipped = failed = 0
        no_image = []
        for a in todo:
            try:
                if rehost_from_url(a):
                    done += 1
                else:
                    skipped += 1
            except NoSourceImage:
                no_image.append(a)
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.WARNING(f"  {a.sku} {a.name!r}: {e}"))
            time.sleep(0.1)
        self.stdout.write(self.style.SUCCESS(
            f"Re-hosted {done}, skipped {skipped} (no source), no image on TCGplayer {len(no_image)}, failed {failed}."))
        in_stock = [a for a in no_image if a.stock > 0]
        if no_image:
            self.stdout.write(
                f"{len(no_image)} product(s) have no TCGplayer photo -- they only need one if you stock them "
                f"(Django admin -> Accessories -> Upload image). In stock now without a photo: {len(in_stock)}")
            for a in in_stock:
                self.stdout.write(f"  {a.sku} {a.name}")
