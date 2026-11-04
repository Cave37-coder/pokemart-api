"""
sync_sealed_catalog -- PokeBulk SA

Imports every Pokemon SEALED product (Booster Boxes, ETBs, Booster Bundles, Tins, Collections, Blisters...)
from TCGCSV (category 3, one group per set) into the Accessory catalog as category "sealed", tagged with its
set name. This feeds the Sealed Collection ("browse a whole set", search, value tracking) -- it is NOT a shop
listing: new rows get stock=0, so customers never see them in the store (same rule as sync_accessories).

Prices = TCGplayer market USD x live USD/ZAR x 1.10, rounded up to R0.50 (same formula as sync_accessories).
Images are re-hosted on R2 (accessories/sealed/<sku>.jpg -- CLAUDE.md "always R2").

  python manage.py sync_sealed_catalog --dry-run
  python manage.py sync_sealed_catalog --skip-images        # fast first pass
  python manage.py sync_sealed_catalog                       # + images (slower; re-runnable, skips done ones)
  python manage.py sync_sealed_catalog --group 24831         # one set only (TCGCSV groupId)
"""
import time

import requests
from django.core.management.base import BaseCommand

from accessories.models import Accessory
from accessories.management.commands.sync_accessories import (
    HEADERS, REQUEST_DELAY_SECONDS, compute_zar_price, get_json, get_usd_zar_rate,
)

TCGCSV = "https://tcgcsv.com/tcgplayer/3"
SEALED_WORDS = (
    "booster", "box", "bundle", "tin", "collection", "elite trainer", "etb", "blister", "display", "deck",
    "case", "binder", "poster", "sticker", "pin", "build & battle", "build and battle", "trove", "stadium",
    "pack", "tech", "case", "vault", "league battle", "battle deck", "starter",
)


def is_sealed(product):
    """Cards carry a 'Number' in extendedData; sealed product does not. Name keywords guard against
    unnumbered oddities (e.g. a stray promo card) sneaking in."""
    ext = {e["name"]: e["value"] for e in product.get("extendedData", [])}
    if ext.get("Number"):
        return False
    name = (product.get("name") or "").lower()
    if name.startswith("code card"):
        return False
    return any(w in name for w in SEALED_WORDS)


class Command(BaseCommand):
    help = "Import Pokemon sealed products from TCGCSV into the Accessory catalog (category=sealed)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-images", action="store_true")
        parser.add_argument("--group", type=int, help="Only this TCGCSV groupId")

    def handle(self, *args, **o):
        from accessories.r2 import rehost_from_url, is_on_r2, NoSourceImage
        rate = get_usd_zar_rate()
        groups = get_json(f"{TCGCSV}/groups").get("results", [])
        if o.get("group"):
            groups = [g for g in groups if g["groupId"] == o["group"]]
        created = updated = skipped = img = img_fail = img_none = 0

        for g in groups:
            gid, gname = g["groupId"], g.get("name", "")
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                products = get_json(f"{TCGCSV}/{gid}/products").get("results", [])
                prices = {p["productId"]: p for p in get_json(f"{TCGCSV}/{gid}/prices").get("results", [])}
            except requests.RequestException as e:
                self.stdout.write(self.style.WARNING(f"[{gname}] fetch failed: {e}"))
                continue

            n_set = 0
            for p in products:
                if not is_sealed(p):
                    continue
                # a sealed product can have several price rows (sub types) -- take the best market price
                mkt = None
                for row in [r for r in prices.values() if r["productId"] == p["productId"]]:
                    m = row.get("marketPrice")
                    if m and (mkt is None or m > mkt):
                        mkt = m
                zar = compute_zar_price(mkt, rate)
                if zar is None:
                    skipped += 1
                    continue
                n_set += 1
                if o["dry_run"]:
                    self.stdout.write(f"  WOULD: [{gname}] {p['name']} -> R{zar}")
                    continue
                obj = Accessory.objects.filter(tcgcsv_product_id=p["productId"]).first()
                was_new = obj is None
                if was_new:
                    obj = Accessory(tcgcsv_product_id=p["productId"], category="sealed", stock=0)
                obj.name = p["name"][:200]
                obj.set_name = gname[:120]
                obj.tcgcsv_category_id = 3
                obj.tcgplayer_url = p.get("url", "") or ""
                obj.source_price_usd = mkt
                if not obj.price_locked or obj.price is None:
                    obj.price = zar
                src = p.get("imageUrl", "") or ""
                if src:
                    obj.image_source_url = src
                obj.save()
                if not o["skip_images"] and not is_on_r2(obj.image_url):
                    try:
                        rehost_from_url(obj, src or None)
                        img += 1
                    except NoSourceImage:
                        img_none += 1
                    except Exception as e:
                        img_fail += 1
                        self.stdout.write(self.style.WARNING(f"  image failed {obj.sku}: {e}"))
                created += was_new
                updated += (not was_new)
            if n_set:
                self.stdout.write(f"[{gname}] {n_set} sealed product(s)")

        self.stdout.write(self.style.SUCCESS(
            f"{'DRY RUN. ' if o['dry_run'] else ''}created {created}, updated {updated}, skipped {skipped} unpriced. "
            f"Images: {img} done, {img_none} none, {img_fail} failed."))
