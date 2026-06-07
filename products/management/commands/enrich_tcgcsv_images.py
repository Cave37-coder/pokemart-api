# -*- coding: utf-8 -*-
"""
enrich_tcgcsv_images.py - PokeBulk SA
Fetches imageUrl from TCGCSV products endpoint for sets not covered by pokemontcg.io.
Only updates: image_url, image_small_url
NEVER touches: price, stock, variant, card_number, name, rarity

Usage:
  python manage.py enrich_tcgcsv_images ALL
  python manage.py enrich_tcgcsv_images MEG ASC CRI
  python manage.py enrich_tcgcsv_images ALL --overwrite
  python manage.py enrich_tcgcsv_images ALL --dry-run

Run with DATABASE_URL uncommented in .env
"""
import requests, time
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import PokemonProduct, CardSet

HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
BASE    = "https://tcgcsv.com/tcgplayer/3"

TCGCSV_IMAGE_SETS = {
    # MEG Era - not yet on pokemontcg.io
    "MEG":      24380,
    "PFL":      24448,
    "MEP":      24451,
    "MEE":      24461,
    "ASC":      24541,
    "POR":      24587,
    "CRI":      24655,
    # SV Era - no ptcgio mapping
    "BLK":      24325,
    "WHT":      24326,
    "SVE":      24382,
    "SVP":      22880,
    # SWSH special sets
    "BRSTG":    3020,
    "ASRTG":    3068,
    "LORTG":    3172,
    "SITTG":    17674,
    "CRZGG":    17689,
    "SHFSV":    2781,
    "HIFSV":    2594,
    # SM special
    "SMP":      1861,
    # Prize Pack
    "PRIZEPACK":22880,
    # Trick or Trade
    "TOT22":    3179,
    "TOT23":    23266,
    "TOT24":    23561,
}


def fetch_tcgcsv_images(group_id):
    """Fetch product imageUrl map from TCGCSV: {product_id: image_url}"""
    try:
        r = requests.get(
            f"{BASE}/{group_id}/products",
            headers=HEADERS, timeout=30
        )
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        products = r.json().get("results", [])
        return {
            p["productId"]: p.get("imageUrl", "") or ""
            for p in products
            if p.get("imageUrl")
        }, None
    except Exception as e:
        return None, str(e)


class Command(BaseCommand):
    help = "Enrich image_url from TCGCSV for sets not covered by pokemontcg.io"

    def add_arguments(self, parser):
        parser.add_argument("set_codes", nargs="+", type=str)
        parser.add_argument("--dry-run",   action="store_true")
        parser.add_argument("--overwrite", action="store_true",
                            help="Overwrite existing images")

    def handle(self, *args, **options):
        codes     = options["set_codes"]
        dry_run   = options["dry_run"]
        overwrite = options["overwrite"]

        if len(codes) == 1 and codes[0].upper() == "ALL":
            codes = list(TCGCSV_IMAGE_SETS.keys())

        codes = [c.upper() for c in codes]

        self.stdout.write("TCGCSV Image Enrichment")
        self.stdout.write(f"Sets: {', '.join(codes)}")
        self.stdout.write(f"Dry run:{dry_run} | Overwrite:{overwrite}")
        self.stdout.write("=" * 60)

        grand_updated = grand_skipped = grand_no_match = 0

        for code in codes:
            gid = TCGCSV_IMAGE_SETS.get(code)
            if not gid:
                self.stdout.write(f"\n[{code}] No TCGCSV group ID - skipping")
                continue

            try:
                db_set = CardSet.objects.get(code=code)
            except CardSet.DoesNotExist:
                self.stdout.write(f"\n[{code}] Not in DB - skipping")
                continue

            self.stdout.write(f"\n[{code}] {db_set.name} (groupId={gid})")

            image_map, error = fetch_tcgcsv_images(gid)
            if error:
                self.stdout.write(f"  TCGCSV error: {error} - skipping")
                continue

            self.stdout.write(f"  TCGCSV images available: {len(image_map)}")

            qs = PokemonProduct.objects.filter(
                card_set=db_set,
                tcgcsv_product_id__isnull=False
            )
            total = qs.count()
            self.stdout.write(f"  DB records with tcgcsv_product_id: {total}")

            if total == 0:
                self.stdout.write(f"  No records with tcgcsv_product_id - skipping")
                continue

            to_update = []
            updated = skipped = no_match = 0

            for p in qs:
                img = image_map.get(p.tcgcsv_product_id, "")

                if not img:
                    no_match += 1
                    continue

                if p.image_url and not overwrite:
                    skipped += 1
                    continue

                if p.image_url == img:
                    skipped += 1
                    continue

                if dry_run:
                    updated += 1
                    continue

                p.image_url = img
                p.image_small_url = img
                to_update.append(p)
                updated += 1

            if to_update and not dry_run:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(
                        to_update,
                        ["image_url", "image_small_url"],
                        batch_size=500
                    )

            self.stdout.write(
                f"  Updated:{updated} | "
                f"Already had image:{skipped} | "
                f"No TCGCSV match:{no_match}"
            )
            grand_updated  += updated
            grand_skipped  += skipped
            grand_no_match += no_match

            time.sleep(0.3)

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"DONE")
        self.stdout.write(f"  Total images updated:  {grand_updated}")
        self.stdout.write(f"  Already had image:     {grand_skipped}")
        self.stdout.write(f"  No TCGCSV match:       {grand_no_match}")
        if dry_run:
            self.stdout.write(f"  (DRY RUN - nothing saved)")
