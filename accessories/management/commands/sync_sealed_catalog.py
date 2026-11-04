"""
sync_sealed_catalog -- PokeBulk SA

Imports every Pokemon SEALED product (Booster Boxes, ETBs, Booster Bundles, Tins, Collections, Blisters...)
from TCGCSV (category 3, one group per set) into the PRODUCT table as supertype "Sealed", so sealed can be
sold through the Pile / checkout / stock / invoices exactly like cards, and be tracked in the Sealed Collection.

  * card_set is left empty on purpose -> checklists, completion and the Pokedex never see sealed rows.
    The set name goes in sealed_set_name, the product type (Booster Box, ETB ...) in card_subtypes.
  * New rows get stock=0 and are hidden from the shop until you set stock (same rule as everything else).
    A re-run refreshes name / set / image / price only -- never stock, never a price_locked price.
  * Prices: TCG market USD x live USD/ZAR x 1.10, rounded up to R0.10 -- the SAME formula as the nightly
    sync_prices_only, which keeps these rows (variant 'N', tcgcsv_product_id) priced from then on.
  * Images are re-hosted on R2 (sealed/products/<productId>.jpg) -- CLAUDE.md "always R2".

  python manage.py sync_sealed_catalog --dry-run
  python manage.py sync_sealed_catalog --skip-images        # fast first pass
  python manage.py sync_sealed_catalog                       # + images (re-runnable; skips ones already on R2)
  python manage.py sync_sealed_catalog --group 24831         # one set only (TCGCSV groupId)
"""
import re
import time
from decimal import Decimal, ROUND_UP

import requests
from django.core.management.base import BaseCommand

from products.models import Category, PokemonProduct
from accessories.management.commands.sync_accessories import (
    REQUEST_DELAY_SECONDS, get_json, get_usd_zar_rate,
)

TCGCSV = "https://tcgcsv.com/tcgplayer/3"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
SEALED_WORDS = (
    "booster", "box", "bundle", "tin", "collection", "elite trainer", "etb", "blister", "display", "deck",
    "case", "binder", "poster", "sticker", "pin", "build & battle", "build and battle", "trove", "stadium",
    "pack", "tech", "vault", "league battle", "starter",
)
# product type, in match order (first hit wins)
TYPES = [
    ("Booster Box Case", ("booster box case", "display case", "case")),
    ("Booster Box", ("booster box", "booster display", "display")),
    ("Elite Trainer Box", ("elite trainer box", "etb")),
    ("Booster Bundle", ("booster bundle",)),
    ("Build & Battle", ("build & battle", "build and battle")),
    ("Tin", ("tin",)),
    ("Blister", ("blister",)),
    ("Booster Pack", ("booster pack", "sleeved booster")),
    ("Deck", ("deck", "starter")),
    ("Collection", ("collection", "box", "pin", "poster", "sticker", "trove", "vault", "binder", "stadium")),
]


def product_type(name):
    n = name.lower()
    for label, words in TYPES:
        # whole-word match so "Showcase" is not a "case" and "Pinsir" is not a "pin"
        if any(re.search(r"(?<![a-z])" + re.escape(w) + r"s?(?![a-z])", n) for w in words):
            return label
    return "Sealed"


def is_sealed(product):
    """Cards carry a 'Number' in extendedData; sealed product does not. Name keywords guard against
    unnumbered oddities (e.g. a stray promo) sneaking in."""
    ext = {e["name"]: e["value"] for e in product.get("extendedData", [])}
    if ext.get("Number"):
        return False
    name = (product.get("name") or "").lower()
    if name.startswith("code card"):
        return False
    return any(re.search(r"(?<![a-z])" + re.escape(w) + r"s?(?![a-z])", name) for w in SEALED_WORDS)


def price_zar(usd, rate):
    if not usd:
        return None
    return (Decimal(str(usd)) * rate * Decimal("1.10") * 10).to_integral_value(rounding=ROUND_UP) / 10


def rehost(pid):
    """Download the TCGplayer product image and put it on R2. Returns the CDN URL, or '' if no image exists."""
    from accessories.r2 import _r2
    src = f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_400w.jpg"
    r = requests.get(src, timeout=20, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    if r.status_code in (403, 404) or not r.content or not r.headers.get("Content-Type", "").startswith("image"):
        return ""
    r.raise_for_status()
    s3, bucket, cdn = _r2()
    key = f"sealed/products/{pid}.jpg"
    s3.put_object(Bucket=bucket, Key=key, Body=r.content, ContentType="image/jpeg")
    return f"{cdn}/{key}"


class Command(BaseCommand):
    help = "Import Pokemon sealed products from TCGCSV as supertype='Sealed' products."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-images", action="store_true")
        parser.add_argument("--group", type=int, help="Only this TCGCSV groupId")

    def handle(self, *args, **o):
        from accessories.r2 import is_on_r2
        rate = Decimal(str(get_usd_zar_rate()))
        groups = get_json(f"{TCGCSV}/groups").get("results", [])
        if o.get("group"):
            groups = [g for g in groups if g["groupId"] == o["group"]]
        category = None if o["dry_run"] else Category.objects.get_or_create(name="Sealed", defaults={"slug": "sealed"})[0]
        created = updated = skipped = img = img_fail = img_none = 0

        for g in groups:
            gid, gname = g["groupId"], g.get("name", "")
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                products = get_json(f"{TCGCSV}/{gid}/products").get("results", [])
                prices = get_json(f"{TCGCSV}/{gid}/prices").get("results", [])
            except requests.RequestException as e:
                self.stdout.write(self.style.WARNING(f"[{gname}] fetch failed: {e}"))
                continue
            best = {}
            for row in prices:   # several sub-type rows per product -> keep the best market price
                m = row.get("marketPrice")
                if m and (row["productId"] not in best or m > best[row["productId"]]):
                    best[row["productId"]] = m

            n_set = 0
            for p in products:
                if not is_sealed(p):
                    continue
                pid = p["productId"]
                zar = price_zar(best.get(pid), rate)
                if zar is None:
                    skipped += 1
                    continue
                n_set += 1
                ptype = product_type(p["name"])
                if o["dry_run"]:
                    self.stdout.write(f"  WOULD: [{gname}] ({ptype}) {p['name']} -> R{zar}")
                    continue
                obj = PokemonProduct.objects.filter(tcgcsv_product_id=pid, supertype="Sealed").first()
                was_new = obj is None
                if was_new:
                    obj = PokemonProduct(tcgcsv_product_id=pid, pb_id=f"SEALED-{pid}", supertype="Sealed",
                                         variant_override="N", condition="NM", stock=0, is_active=True,
                                         category=category, rarity="common")
                obj.name = p["name"][:200]
                obj.sealed_set_name = gname[:120]
                obj.card_subtypes = ptype
                if not obj.price_locked or not obj.price:
                    obj.price = zar
                    obj.price_normal = zar
                obj.save()
                if not o["skip_images"] and not is_on_r2(obj.image_url):
                    try:
                        url = rehost(pid)
                        if url:
                            PokemonProduct.objects.filter(pk=obj.pk).update(image_url=url, image_small_url=url)
                            img += 1
                        else:
                            img_none += 1
                    except Exception as e:
                        img_fail += 1
                        self.stdout.write(self.style.WARNING(f"  image failed {pid}: {e}"))
                created += was_new
                updated += (not was_new)
            if n_set:
                self.stdout.write(f"[{gname}] {n_set} sealed product(s)")

        self.stdout.write(self.style.SUCCESS(
            f"{'DRY RUN. ' if o['dry_run'] else ''}created {created}, updated {updated}, skipped {skipped} unpriced. "
            f"Images: {img} done, {img_none} none, {img_fail} failed."))
        if created:
            self.stdout.write(self.style.WARNING("New sealed products have stock 0 (hidden from customers) until you set stock."))
