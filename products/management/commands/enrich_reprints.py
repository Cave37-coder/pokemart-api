# -*- coding: utf-8 -*-
"""
enrich_reprints.py - PokeBulk SA
Enriches Prize Pack, Trick or Trade and other reprint sets by:
1. Fetching card info from TCGCSV (name, number, image)
2. Cross-referencing the original card in DB by card number + name
3. Copying enrichment data (attacks, abilities, HP etc) from original
4. Storing the stamped image from TCGCSV

NEVER touches: price, stock, variant, card_number, rarity

Usage:
  python manage.py enrich_reprints PRIZEPACK
  python manage.py enrich_reprints TOT22 TOT23 TOT24
  python manage.py enrich_reprints ALL
  python manage.py enrich_reprints PRIZEPACK --dry-run
  python manage.py enrich_reprints PRIZEPACK --verify-only

Run with DATABASE_URL uncommented in .env
"""
import requests, re
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import PokemonProduct, CardSet

HEADERS     = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"

# Reprint sets - DB code -> TCGCSV group ID
REPRINT_SETS = {
    "PRIZEPACK": 22880,
    "TOT22":     3179,
    "TOT23":     23266,
    "TOT24":     23561,
    "TK1":       None,
    "TK2":       None,
    "TK24":      None,
}

# Sets to exclude when searching for original cards
REPRINT_SET_CODES = [
    "PRIZEPACK", "TOT22", "TOT23", "TOT24",
    "TK1", "TK2", "TK24",
]

ENRICH_FIELDS = [
    "image_url", "image_small_url",
    "hp", "card_subtypes", "supertype",
    "weakness_type", "weakness_value",
    "resistance_type", "resistance_value",
    "retreat_cost", "artist",
    "ability_name", "ability_type", "ability_text",
    "attack_1_name", "attack_1_damage", "attack_1_text",
    "attack_2_name", "attack_2_damage", "attack_2_text",
    "pokedex_number", "flavour_text",
]


def fetch_tcgcsv_products(group_id):
    """Fetch all products from TCGCSV group"""
    try:
        r = requests.get(
            f"{TCGCSV_BASE}/{group_id}/products",
            headers=HEADERS, timeout=30
        )
        if r.status_code != 200:
            return None
        return r.json().get("results", [])
    except Exception:
        return None


def parse_card_num(number_str):
    """Extract card number integer from 006/163 -> 6"""
    if not number_str:
        return None
    try:
        return int(number_str.split("/")[0])
    except Exception:
        return None


def clean_name(card_name):
    """Remove number suffixes from card name"""
    return re.sub(r'\s*-\s*\d+/\d+\s*$', '', card_name).strip()


def find_original_card(card_name, number_str):
    """
    Find original card in DB by card number + name.
    Excludes reprint sets from search.
    Falls back to name-only if number match fails.
    """
    card_num = parse_card_num(number_str)
    name     = clean_name(card_name)

    # Try card number + exact name first
    if card_num:
        match = PokemonProduct.objects.filter(
            card_number=card_num,
            name__iexact=name
        ).exclude(
            card_set__code__in=REPRINT_SET_CODES
        ).first()
        if match:
            return match

        # Try card number + contains name
        match = PokemonProduct.objects.filter(
            card_number=card_num,
            name__icontains=name
        ).exclude(
            card_set__code__in=REPRINT_SET_CODES
        ).first()
        if match:
            return match

    # Fallback - name only (less reliable but catches edge cases)
    match = PokemonProduct.objects.filter(
        name__iexact=name
    ).exclude(
        card_set__code__in=REPRINT_SET_CODES
    ).first()
    return match


class Command(BaseCommand):
    help = "Enrich reprint sets (Prize Pack, TOT) by cross-referencing original cards"

    def add_arguments(self, parser):
        parser.add_argument("set_codes", nargs="+", type=str)
        parser.add_argument("--dry-run",     action="store_true")
        parser.add_argument("--verify-only", action="store_true",
                            help="Test first 5 cards only")
        parser.add_argument("--overwrite",   action="store_true",
                            help="Overwrite existing data")

    def handle(self, *args, **options):
        codes     = options["set_codes"]
        dry_run   = options["dry_run"]
        verify    = options["verify_only"]
        overwrite = options["overwrite"]

        if len(codes) == 1 and codes[0].upper() == "ALL":
            codes = list(REPRINT_SETS.keys())

        codes = [c.upper() for c in codes]

        self.stdout.write("Reprint Set Enrichment (Prize Pack / TOT)")
        self.stdout.write(f"Sets: {', '.join(codes)}")
        self.stdout.write("=" * 60)

        grand_updated = grand_not_found = grand_no_original = 0

        for code in codes:
            gid = REPRINT_SETS.get(code)
            if gid is None:
                self.stdout.write(f"\n[{code}] No TCGCSV group ID - skipping")
                continue

            try:
                db_set = CardSet.objects.get(code=code)
            except CardSet.DoesNotExist:
                self.stdout.write(f"\n[{code}] Not in DB - skipping")
                continue

            self.stdout.write(f"\n[{code}] {db_set.name} (groupId={gid})")

            # Fetch from TCGCSV
            products = fetch_tcgcsv_products(gid)
            if not products:
                self.stdout.write(f"  TCGCSV fetch failed - skipping")
                continue

            self.stdout.write(f"  TCGCSV products: {len(products)}")

            if verify:
                products = products[:5]

            to_update = []
            updated = not_found = no_original = 0

            for tcg_product in products:
                pid        = tcg_product["productId"]
                card_name  = tcg_product.get("name", "").strip()
                image_url  = tcg_product.get("imageUrl", "") or ""
                number_str = next(
                    (e["value"] for e in tcg_product.get("extendedData", [])
                     if e["name"] == "Number"),
                    ""
                )

                # Skip non-card products (bundles, packs etc - no number)
                if not number_str:
                    continue

                # Find DB record for this reprint
                db_record = PokemonProduct.objects.filter(
                    card_set=db_set,
                    tcgcsv_product_id=pid
                ).first()

                if not db_record:
                    not_found += 1
                    if verify:
                        self.stdout.write(
                            f"  NOT IN DB: {card_name} {number_str} pid={pid}"
                        )
                    continue

                # Find original card to copy data from
                original = find_original_card(card_name, number_str)

                if not original:
                    no_original += 1
                    if verify:
                        self.stdout.write(
                            f"  NO ORIGINAL: {card_name} {number_str}"
                        )
                    # Still update image even without original
                    if image_url and (overwrite or not db_record.image_url):
                        if not dry_run:
                            db_record.image_url = image_url
                            db_record.image_small_url = image_url
                            to_update.append(db_record)
                    continue

                if verify:
                    self.stdout.write(
                        f"  MATCHED: {card_name} {number_str} -> "
                        f"{original.card_set.code} #{original.card_number} "
                        f"HP:{original.hp} Artist:{original.artist}"
                    )
                    continue

                if dry_run:
                    updated += 1
                    continue

                changed = False

                # Always update image from TCGCSV (stamped version)
                if image_url and (overwrite or not db_record.image_url):
                    db_record.image_url = image_url
                    db_record.image_small_url = image_url
                    changed = True

                # Copy enrichment data from original
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
                    orig_val = getattr(original, field, None)
                    curr_val = getattr(db_record, field, None)
                    if orig_val and (overwrite or not curr_val):
                        setattr(db_record, field, orig_val)
                        changed = True

                if changed:
                    to_update.append(db_record)
                    updated += 1

                # Batch save every 100
                if len(to_update) >= 100:
                    with transaction.atomic():
                        PokemonProduct.objects.bulk_update(
                            to_update, ENRICH_FIELDS, batch_size=200
                        )
                    self.stdout.write(
                        f"  Saved {len(to_update)} records..."
                    )
                    to_update = []

            # Save remaining
            if to_update and not dry_run:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(
                        to_update, ENRICH_FIELDS, batch_size=200
                    )

            self.stdout.write(
                f"  Updated:{updated} | "
                f"Not in DB:{not_found} | "
                f"No original found:{no_original}"
            )
            grand_updated     += updated
            grand_not_found   += not_found
            grand_no_original += no_original

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"DONE")
        self.stdout.write(f"  Total updated:      {grand_updated}")
        self.stdout.write(f"  Not in DB:          {grand_not_found}")
        self.stdout.write(f"  No original found:  {grand_no_original}")
        if dry_run:
            self.stdout.write(f"  (DRY RUN - nothing saved)")