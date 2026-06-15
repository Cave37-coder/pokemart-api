# -*- coding: utf-8 -*-
"""
import_tot_sets.py
Imports Trick or Trade sets from TCGCSV into the DB.
Creates PokemonProduct records with correct variant codes.
Uses cross-reference to find original card data.

Usage:
  python import_tot_sets.py
  python import_tot_sets.py --dry-run

Run with DATABASE_URL uncommented in .env
"""
import os, django, requests, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet
from django.db import transaction

HEADERS     = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"

TOT_SETS = {
    "TOT22": 3179,
    "TOT23": 23266,
    "TOT24": 23561,
}

# Reprint set codes to exclude when finding originals
REPRINT_CODES = [
    "PRIZEPACK","TOT22","TOT23","TOT24","TK1","TK2","TK24"
]

def fetch_tcgcsv_products(group_id):
    r = requests.get(
        f"{TCGCSV_BASE}/{group_id}/products",
        headers=HEADERS, timeout=30
    )
    if r.status_code != 200:
        return []
    return r.json().get("results", [])

def fetch_tcgcsv_prices(group_id):
    """Returns {product_id: {subTypeName: marketPrice}}"""
    r = requests.get(
        f"{TCGCSV_BASE}/{group_id}/prices",
        headers=HEADERS, timeout=30
    )
    if r.status_code != 200:
        return {}
    prices = {}
    for row in r.json().get("results", []):
        pid = row["productId"]
        sub = row.get("subTypeName", "Normal")
        if pid not in prices:
            prices[pid] = {}
        prices[pid][sub] = row.get("marketPrice") or row.get("midPrice") or 0
    return prices

def parse_card_num(number_str):
    if not number_str:
        return None
    try:
        return int(number_str.split("/")[0])
    except Exception:
        return None

def clean_name(name):
    return re.sub(r'\s*-\s*\d+/\d+\s*$', '', name).strip()

def find_original(card_name, number_str):
    card_num = parse_card_num(number_str)
    name = clean_name(card_name)

    if card_num:
        match = PokemonProduct.objects.filter(
            card_number=card_num,
            name__iexact=name
        ).exclude(card_set__code__in=REPRINT_CODES).first()
        if match:
            return match

        match = PokemonProduct.objects.filter(
            card_number=card_num,
            name__icontains=name
        ).exclude(card_set__code__in=REPRINT_CODES).first()
        if match:
            return match

    match = PokemonProduct.objects.filter(
        name__iexact=name
    ).exclude(card_set__code__in=REPRINT_CODES).first()
    return match

def variant_code_from_subtype(subtype):
    """Map TCGCSV subTypeName to our variant code"""
    mapping = {
        "Normal":         "N",
        "Holofoil":       "H",
        "Reverse Holofoil":"RH",
        "1st Edition":    "N",
    }
    return mapping.get(subtype, "N")

def import_tot_set(set_code, group_id, dry_run=False):
    print(f"\n[{set_code}] groupId={group_id}")

    try:
        db_set = CardSet.objects.get(code=set_code)
    except CardSet.DoesNotExist:
        print(f"  ERROR: {set_code} not in DB")
        return

    existing = PokemonProduct.objects.filter(card_set=db_set).count()
    print(f"  Existing records: {existing}")

    # Fetch products and prices
    print(f"  Fetching products from TCGCSV...")
    products = fetch_tcgcsv_products(group_id)
    print(f"  Got {len(products)} products")

    print(f"  Fetching prices from TCGCSV...")
    prices = fetch_tcgcsv_prices(group_id)
    print(f"  Got prices for {len(prices)} products")

    to_create = []
    created = skipped = no_original = 0

    for p in products:
        pid        = p["productId"]
        card_name  = p.get("name", "").strip()
        image_url  = p.get("imageUrl", "") or ""
        number_str = next(
            (e["value"] for e in p.get("extendedData", [])
             if e["name"] == "Number"), ""
        )
        rarity = next(
            (e["value"] for e in p.get("extendedData", [])
             if e["name"] == "Rarity"), ""
        )

        # Skip non-card products
        if not number_str:
            continue

        card_num = parse_card_num(number_str)

        # Skip if already in DB
        if PokemonProduct.objects.filter(
            card_set=db_set,
            tcgcsv_product_id=pid
        ).exists():
            skipped += 1
            continue

        # Find original card for enrichment data
        original = find_original(card_name, number_str)

        # Get price - TOT cards are typically Normal variant
        product_prices = prices.get(pid, {})
        market_price   = product_prices.get("Normal", 0) or 0

        # Build product record
        name_clean = clean_name(card_name)

        product = PokemonProduct(
            card_set            = db_set,
            name                = name_clean,
            card_number         = card_num,
            variant_override    = "N",  # TOT cards are always Normal stamped
            tcgcsv_product_id   = pid,
            image_url           = image_url,
            image_small_url     = image_url,
            rarity              = rarity,
            price               = market_price,
            stock               = 0,
            pb_id               = f"TCGCSV-{pid}",
        )

        # Copy enrichment data from original if found
        if original:
            fields_to_copy = [
                "hp", "supertype", "card_subtypes",
                "weakness_type", "weakness_value",
                "resistance_type", "resistance_value",
                "retreat_cost", "artist",
                "ability_name", "ability_type", "ability_text",
                "attack_1_name", "attack_1_damage", "attack_1_text",
                "attack_2_name", "attack_2_damage", "attack_2_text",
                "pokedex_number", "flavour_text",
            ]
            for field in fields_to_copy:
                val = getattr(original, field, None)
                if val:
                    setattr(product, field, val)
            print(
                f"  CREATE: {name_clean} {number_str} "
                f"-> original: {original.card_set.code} #{original.card_number}"
            )
        else:
            no_original += 1
            print(f"  CREATE (no original): {name_clean} {number_str}")

        to_create.append(product)
        created += 1

    if not dry_run and to_create:
        with transaction.atomic():
            PokemonProduct.objects.bulk_create(to_create, batch_size=200, ignore_conflicts=True)
        print(f"  Saved {len(to_create)} records")
    elif dry_run:
        print(f"  DRY RUN - would create {len(to_create)} records")

    print(
        f"  Created:{created} | "
        f"Skipped (exists):{skipped} | "
        f"No original:{no_original}"
    )


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv

    print("TOT Set Import")
    print(f"Dry run: {dry_run}")
    print("=" * 60)

    for set_code, group_id in TOT_SETS.items():
        import_tot_set(set_code, group_id, dry_run=dry_run)

    print("\nDone.")
