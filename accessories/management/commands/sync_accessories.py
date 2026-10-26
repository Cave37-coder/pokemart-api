"""
accessories/management/commands/sync_accessories.py

Imports Pokemon-related accessories (sleeves, deck boxes, playmats,
storage, etc.) from TCGCSV -- the same public catalog API that already
feeds the card catalog (see sync_tcgcsv.py / pull_pokemon_sleeves.py from
an earlier session). Michael confirmed 2026-08-07 there's no separate live
PoBuSA/POS API to pull from yet, so this goes straight to the source.

Covers every game-agnostic TCGCSV "supplies" category (accessories aren't
listed under Pokemon's own categoryId=3 -- they're shared across every TCG
TCGplayer carries), filtered down to Pokemon-branded products by name/group
keyword match, same approach validated in pull_pokemon_sleeves.py.

IMPORTANT -- stock is deliberately NEVER set by this import, on either a
fresh insert (stays 0, i.e. invisible to customers per the
"only see what's in Stock" rule) or a re-sync of an existing row (left
exactly as Michael last set it in admin). TCGCSV is a price/catalog
aggregator, not Michael's till -- it has no idea how many units he actually
has on the shelf. Setting real stock counts is a deliberate, separate,
manual step in Django admin, same convention as pos_stock -> stock for
cards. Only catalog metadata (name/price/image/description) refreshes on
re-sync.

Usage:
    python manage.py sync_accessories                  # all categories
    python manage.py sync_accessories --category 31     # just Card Sleeves
    python manage.py sync_accessories --all-brands       # skip the Pokemon keyword filter
    python manage.py sync_accessories --dry-run
    python manage.py sync_accessories --skip-images     # catalog/price only, no R2 uploads

2026-10-26 changes:
  * Images: the TCGplayer image is downloaded and re-hosted on R2
    (accessories/<category>/<sku>.jpg) for new rows and for any row whose
    image is still external -- CLAUDE.md "always R2". The original URL is
    kept in image_source_url. Rows already on R2 are left alone (so a
    photo Michael uploaded himself is never replaced).
  * Prices: rows with price_locked=True (price set by hand in admin, or by a
    completed buying invoice's sell price) keep their price.
"""
import math
import time

import requests
from django.core.management.base import BaseCommand

from accessories.models import Accessory

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
REQUEST_DELAY_SECONDS = 0.3
USER_AGENT = "PokeBulkSA-AccessorySync/1.0 (enquiries@pokebulk.co.za)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

POKEMON_KEYWORDS = ["pokemon", "pokémon", "pikachu", "eevee", "charizard", "gengar"]

# Confirmed via https://tcgcsv.com/tcgplayer/categories, 2026-08-07 -- the
# game-agnostic supply/storage categories, same list sync_tcgcsv.py's
# ACCESSORY_CATEGORY_IDS uses. Maps TCGCSV categoryId -> our Accessory.category key.
ACCESSORY_CATEGORY_IDS = {
    14: "supplies",
    31: "sleeves",
    32: "deck_boxes",
    33: "storage_tins",
    34: "life_counters",
    35: "playmats",
    49: "protective_pages",
    50: "storage_albums",
    51: "collectible_storage",
    52: "supply_bundles",
    82: "supplies",
}


def get_json(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def is_pokemon_related(group_name, product_name):
    haystack = f"{group_name} {product_name}".lower()
    return any(kw in haystack for kw in POKEMON_KEYWORDS)


def get_usd_zar_rate():
    """3-source fallback chain, matching the documented pricing pipeline
    (same as pull_pokemon_sleeves.py)."""
    for label, url, path in [
        ("Frankfurter (ECB)", "https://api.frankfurter.app/latest?from=USD&to=ZAR", ("rates", "ZAR")),
        ("ExchangeRate-API", "https://open.er-api.com/v6/latest/USD", ("rates", "ZAR")),
        ("fawazahmed0 CDN", "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", ("usd", "zar")),
    ]:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            rate = data[path[0]][path[1]]
            print(f"USD/ZAR rate from {label}: {rate}")
            return float(rate)
        except Exception as e:
            print(f"{label} failed: {e}")
    print("WARNING: all 3 rate sources failed. Falling back to a hardcoded estimate -- VERIFY before trusting prices.")
    return 18.0


def compute_zar_price(market_usd, zar_rate):
    if market_usd is None or market_usd == "":
        return None
    try:
        market_usd = float(market_usd)
    except (TypeError, ValueError):
        return None
    raw = max(market_usd * zar_rate * 1.10, 1.50)
    return math.ceil(raw * 2) / 2  # round UP to nearest R0.50


class Command(BaseCommand):
    help = "Imports Pokemon-related accessories from TCGCSV into the Accessory catalog."

    def add_arguments(self, parser):
        parser.add_argument("--category", type=int, help="Only sync this TCGCSV categoryId")
        parser.add_argument("--all-brands", action="store_true", help="Skip the Pokemon keyword filter (imports every brand)")
        parser.add_argument("--dry-run", action="store_true", help="Print what would happen, write nothing")
        parser.add_argument("--skip-images", action="store_true", help="Don't download/re-host images on R2")

    def handle(self, *args, **options):
        only_pokemon = not options["all_brands"]
        dry_run = options["dry_run"]
        skip_images = options["skip_images"]
        from accessories.r2 import rehost_from_url, is_on_r2, NoSourceImage
        img_done = img_failed = img_missing = 0
        categories = (
            {options["category"]: ACCESSORY_CATEGORY_IDS[options["category"]]}
            if options.get("category")
            else ACCESSORY_CATEGORY_IDS
        )

        zar_rate = get_usd_zar_rate()
        created, updated, skipped = 0, 0, 0

        for cat_id, our_category in categories.items():
            self.stdout.write(f"\n=== TCGCSV categoryId={cat_id} -> Accessory.category={our_category!r} ===")
            try:
                groups = get_json(f"{TCGCSV_BASE}/{cat_id}/groups").get("results", [])
            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(f"  Failed to fetch groups: {e}"))
                continue

            for group in groups:
                group_id = group["groupId"]
                group_name = group.get("name", "")
                time.sleep(REQUEST_DELAY_SECONDS)

                try:
                    products = get_json(f"{TCGCSV_BASE}/{cat_id}/{group_id}/products").get("results", [])
                except requests.RequestException as e:
                    self.stdout.write(self.style.WARNING(f"  [{group_name}] products fetch failed: {e}"))
                    continue

                time.sleep(REQUEST_DELAY_SECONDS)
                try:
                    prices = {
                        p["productId"]: p
                        for p in get_json(f"{TCGCSV_BASE}/{cat_id}/{group_id}/prices").get("results", [])
                    }
                except requests.RequestException as e:
                    self.stdout.write(self.style.WARNING(f"  [{group_name}] prices fetch failed: {e}"))
                    prices = {}

                for p in products:
                    name = p.get("name", "")
                    if only_pokemon and not is_pokemon_related(group_name, name):
                        skipped += 1
                        continue

                    price_info = prices.get(p["productId"], {})
                    market_usd = price_info.get("marketPrice")
                    zar_price = compute_zar_price(market_usd, zar_rate)
                    if zar_price is None:
                        skipped += 1
                        continue

                    extended = {e["name"]: e["value"] for e in p.get("extendedData", [])}
                    manufacturer = extended.get("Manufacturer", extended.get("Brand", ""))[:100]

                    if dry_run:
                        self.stdout.write(f"  WOULD sync: {name!r} -> R{zar_price} (tcgcsv_product_id={p['productId']})")
                        continue

                    source_img = p.get("imageUrl", "") or ""
                    obj = Accessory.objects.filter(tcgcsv_product_id=p["productId"]).first()
                    was_created = obj is None
                    if was_created:
                        obj = Accessory(tcgcsv_product_id=p["productId"], category=our_category)
                    # Category is only set on create -- a row Michael moved
                    # (e.g. to "sealed") stays where he put it.
                    obj.name = name
                    obj.manufacturer = manufacturer
                    obj.tcgcsv_category_id = cat_id
                    obj.tcgplayer_url = p.get("url", "") or ""
                    obj.source_price_usd = market_usd
                    if not obj.price_locked or obj.price is None:
                        obj.price = zar_price
                    if source_img:
                        obj.image_source_url = source_img
                    # stock intentionally never set here -- see module docstring.
                    obj.save()

                    if not skip_images and not is_on_r2(obj.image_url) and (source_img or obj.image_source_url):
                        try:
                            rehost_from_url(obj, source_img or None)
                            img_done += 1
                        except NoSourceImage:
                            img_missing += 1
                        except Exception as e:
                            img_failed += 1
                            self.stdout.write(self.style.WARNING(f"  image re-host failed for {obj.sku} ({name}): {e}"))

                    if was_created:
                        created += 1
                    else:
                        updated += 1

            self.stdout.write(f"  -> done with categoryId={cat_id}")

        self.stdout.write(self.style.SUCCESS(
            f"\n{'DRY RUN — nothing written. ' if dry_run else ''}"
            f"Created {created}, updated {updated}, skipped {skipped} non-matching product(s). "
            f"Images re-hosted on R2: {img_done} (no TCGplayer photo {img_missing}, failed {img_failed})."
        ))
        if created:
            self.stdout.write(self.style.WARNING(
                f"{created} new accessories were created with stock=0 (hidden from customers). "
                f"Set real stock counts in Django admin before they'll appear on the site."
            ))
