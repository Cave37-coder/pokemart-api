import math, time, requests
from decimal import Decimal, ROUND_UP
from django.core.management.base import BaseCommand
from django.db import transaction

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")

# TCGCSV variant name -> DB variant_override code
VARIANT_MAP = {
    'Normal':             'N',
    'Reverse Holofoil':   'RH',
    'Holofoil':           'H',
    '1st Edition Holofoil': 'H',
    'Unlimited Holofoil': 'H',
    '1st Edition':        'N',
    'Unlimited':          'N',
}

class Command(BaseCommand):
    help = "Nightly price-only sync from TCGCSV"

    def handle(self, *args, **options):
        from products.models import PokemonProduct

        # Fetch live USD/ZAR rate
        rate = Decimal("18.50")
        for url in ["https://api.exchangerate-api.com/v4/latest/USD", "https://open.er-api.com/v6/latest/USD"]:
            try:
                r = requests.get(url, timeout=10)
                zar = r.json().get("rates", {}).get("ZAR")
                if zar:
                    rate = Decimal(str(zar))
                    break
            except Exception:
                continue
        self.stdout.write(f"1 USD = R{rate}")

        # Fetch all groups from TCGCSV
        self.stdout.write("Fetching groups from TCGCSV...")
        r = requests.get(f"{TCGCSV_BASE}/groups", headers=HEADERS, timeout=30)
        groups = r.json()
        if isinstance(groups, dict):
            groups = groups.get("results", groups.get("data", []))
        self.stdout.write(f"  {len(groups)} groups found")

        # Build map: (tcgcsv_product_id, variant_override) -> product
        self.stdout.write("Loading products from DB...")
        all_products = PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True)
        pid_variant_map = {}
        pid_map = {}  # fallback: productId only
        for p in all_products:
            key = (p.tcgcsv_product_id, p.variant_override or 'N')
            pid_variant_map[key] = p
            # fallback for cards with no variant
            if p.tcgcsv_product_id not in pid_map:
                pid_map[p.tcgcsv_product_id] = p
        self.stdout.write(f"  {len(pid_variant_map):,} products loaded")

        def round_up_10c(zar):
            # Round UP to nearest R0.10
            return (Decimal(str(zar)) * 10).to_integral_value(rounding=ROUND_UP) / 10

        updated = skipped = no_match = 0
        to_update = []

        for i, g in enumerate(groups, 1):
            gid = g.get("groupId") or g.get("id")
            try:
                r = requests.get(f"{TCGCSV_BASE}/{gid}/prices", headers=HEADERS, timeout=30)
                prices = r.json()
                if isinstance(prices, dict):
                    prices = prices.get("results", prices.get("data", []))
                if not isinstance(prices, list):
                    continue
            except Exception:
                continue

            for row in prices:
                pid = row.get("productId")
                if not pid:
                    continue
                pid = int(pid)

                # Get variant from TCGCSV and map to DB code
                tcg_variant = row.get("subTypeName") or row.get("printing") or "Normal"
                db_variant = VARIANT_MAP.get(tcg_variant, 'N')

                # Try exact (productId, variant) match first, fallback to productId only
                p = pid_variant_map.get((pid, db_variant)) or pid_map.get(pid)
                if p is None:
                    no_match += 1
                    continue

                usd = row.get("midPrice") or row.get("marketPrice") or row.get("lowPrice")
                if not usd or float(usd) <= 0:
                    continue

                new_price = round_up_10c(Decimal(str(usd)) * rate * MARKUP)
                if p.price == new_price:
                    skipped += 1
                    continue

                p.price = new_price
                to_update.append(p)
                updated += 1

            if len(to_update) >= 2000:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(to_update, ["price"])
                self.stdout.write(f"  ...wrote {updated:,}")
                to_update = []

            time.sleep(0.2)

        if to_update:
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(to_update, ["price"])

        self.stdout.write(f"Done. Updated={updated:,} Skipped={skipped:,} No match={no_match:,}")
