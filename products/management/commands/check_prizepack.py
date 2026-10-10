"""
check_prizepack.py - PokeBulk SA

Compares TCGplayer's "Prize Pack Series Cards" group (TCGCSV group 22880 --
ALL series, incl. Series 9 which launched 2026-07-01) against what is in our
database, so we can see which Prize Pack cards are missing or have no image.

A product counts as "in the DB" if ANY row has that tcgcsv_product_id or
pb_id == 'TCGCSV-<id>' (rows may have been moved to their home set by
link_prizepack_to_home, so this looks across all sets, not just PRIZEPACK).

  python manage.py check_prizepack
  python manage.py check_prizepack --show 60
"""
import requests
from django.core.management.base import BaseCommand

from products.models import PokemonProduct, CardSet

URL = "https://tcgcsv.com/tcgplayer/3/22880/products"
UA = {"User-Agent": "PokeBulkSA-PrizePackCheck/1.0 (https://pokebulk.co.za)"}
R2 = "https://images.pokebulk.co.za/"


class Command(BaseCommand):
    help = "Compare TCGplayer Prize Pack cards with the database (missing cards / images)."

    def add_arguments(self, parser):
        parser.add_argument("--show", type=int, default=40, help="How many missing products to list")

    def handle(self, *args, **o):
        r = requests.get(URL, headers=UA, timeout=60)
        r.raise_for_status()
        prods = r.json().get("results", [])
        # skip sealed product (boxes/packs) -- singles have a Number in extendedData
        def ext(p, key):
            for e in p.get("extendedData", []) or []:
                if e.get("name") == key:
                    return e.get("value")
            return None
        singles = [p for p in prods if ext(p, "Number")]
        self.stdout.write(f"TCGCSV group 22880: {len(prods)} products, {len(singles)} cards (have a Number)")

        have = set()
        for tid, pb in PokemonProduct.objects.values_list("tcgcsv_product_id", "pb_id"):
            if tid:
                have.add(int(tid))
            if pb and pb.startswith("TCGCSV-") and pb[7:].isdigit():
                have.add(int(pb[7:]))

        missing = [p for p in singles if p["productId"] not in have]
        self.stdout.write(f"In DB: {len(singles) - len(missing)}   MISSING from DB: {len(missing)}")
        for p in sorted(missing, key=lambda x: -x["productId"])[: o["show"]]:
            self.stdout.write(f"  {p['productId']}  {p['name'][:50]:50}  #{ext(p, 'Number')}  {ext(p, 'Rarity') or ''}")

        pp = CardSet.objects.filter(code="PRIZEPACK").first()
        if pp:
            qs = PokemonProduct.objects.filter(card_set=pp)
            total = qs.count()
            r2 = qs.filter(image_url__startswith=R2).count()
            blank = qs.filter(image_url="").count()
            self.stdout.write(f"\nPRIZEPACK set in DB: {total} rows | images on R2: {r2} | blank: {blank} "
                              f"| external/other: {total - r2 - blank}")
        newest = sorted(singles, key=lambda x: -x["productId"])[:8]
        self.stdout.write("\nNewest TCGplayer Prize Pack products (highest ids ~ latest series):")
        for p in newest:
            self.stdout.write(f"  {p['productId']}  {p['name'][:50]:50}  #{ext(p, 'Number')}  "
                              f"{'in DB' if p['productId'] in have else 'MISSING'}")
