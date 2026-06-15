"""
Run from C:\Users\texca\pokemart-api:
    python write_sync_prices.py

This creates products/management/commands/sync_prices.py
and ensures the __init__.py files are in place.
"""
import os

# Ensure directories + __init__ files exist
for d in [
    "products/management",
    "products/management/commands",
]:
    os.makedirs(d, exist_ok=True)

for f in [
    "products/management/__init__.py",
    "products/management/commands/__init__.py",
]:
    if not os.path.exists(f):
        open(f, "w").close()
        print(f"Created {f}")

CONTENT = r'''import math
import time
import requests
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import CardSet, PokemonProduct


TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
POKEMON_CATEGORY = 3
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/USD"
MARKUP = Decimal("1.1")

PRINTING_TO_VARIANT = {
    "Normal":                 "N",
    "Holofoil":               "H",
    "Reverse Holofoil":       "RH",
    "1st Edition Normal":     "1st",
    "1st Edition Holofoil":   "1st",
    "1st Edition":            "1st",
    "Unlimited Normal":       "N",
    "Unlimited Holofoil":     "H",
    "Double Rare":            "DR",
    "Art Rare":               "AS",
    "Special Art Rare":       "SIR",
    "Illustration Rare":      "IR",
    "Hyper Rare":             "HR",
    "Master Ball Holofoil":   "RH",
    "Poke Ball Holofoil":     "RH",
    "Mirror Holofoil":        "MH",
}

RH_BUCKET = {"RH", "RH-PB", "RH-MB", "BRH-FB", "BRH-LB", "BRH-QB", "BRH-DB", "BRH-R", "ERH"}


def round_up_to_50_cents(zar: Decimal) -> Decimal:
    doubled = zar * 2
    ceiled = Decimal(math.ceil(doubled))
    return ceiled / 2


def to_zar(usd: Decimal, rate: Decimal) -> Decimal:
    return round_up_to_50_cents(usd * rate * MARKUP)


def fetch_exchange_rate() -> Decimal:
    try:
        resp = requests.get(EXCHANGE_RATE_API, timeout=10)
        resp.raise_for_status()
        return Decimal(str(resp.json()["rates"]["ZAR"]))
    except Exception as exc:
        raise CommandError(f"Could not fetch exchange rate: {exc}")


def fetch_tcgcsv_groups() -> list:
    url = f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/groups"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", data) if isinstance(data, dict) else data


def fetch_prices_for_group(group_id: int) -> list:
    url = f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/{group_id}/prices"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", data) if isinstance(data, dict) else data


def build_name_key(name: str, number: str) -> str:
    return f"{name.strip().lower()}|{str(number).strip().lstrip('0')}"


def _resolve_usd_for_variant(variant: str, variant_usd_map: dict):
    if not variant:
        variant = "N"
    if variant in variant_usd_map:
        return variant_usd_map[variant]
    if variant in RH_BUCKET and "RH" in variant_usd_map:
        return variant_usd_map["RH"]
    if variant == "MH" and "H" in variant_usd_map:
        return variant_usd_map["H"]
    for fallback in ("H", "N"):
        if fallback in variant_usd_map:
            return variant_usd_map[fallback]
    return None


def sync_set_prices(card_set, group_prices, rate, dry_run, stdout, style):
    stats = {"matched": 0, "updated": 0, "skipped": 0, "unmatched": 0}

    products = PokemonProduct.objects.filter(card_set=card_set)
    product_map = {}
    for p in products:
        key = build_name_key(p.name, p.card_number)
        product_map[key] = p

    if not product_map:
        stdout.write(style.WARNING(f"  No products for {card_set.code}"))
        return stats

    card_prices = {}
    for row in group_prices:
        condition = row.get("condition", "")
        if condition and condition != "Near Mint":
            continue
        printing = row.get("printing", "Normal") or "Normal"
        variant_code = PRINTING_TO_VARIANT.get(printing)
        if not variant_code:
            pl = printing.lower()
            if "reverse" in pl:
                variant_code = "RH"
            elif "holo" in pl:
                variant_code = "H"
            elif "1st" in pl or "first" in pl:
                variant_code = "1st"
            else:
                variant_code = "N"

        name = row.get("name", "").strip()
        number = str(row.get("number", "")).strip().lstrip("0") or ""
        market = row.get("marketPrice")
        low = row.get("lowPrice")
        usd_raw = market if market is not None else low
        if usd_raw is None:
            continue
        usd = Decimal(str(usd_raw))
        if usd <= 0:
            continue

        key = build_name_key(name, number)
        if key not in card_prices:
            card_prices[key] = {}
        existing = card_prices[key].get(variant_code, Decimal("0"))
        if usd > existing:
            card_prices[key][variant_code] = usd

    updates = []
    for key, variant_usd_map in card_prices.items():
        product = product_map.get(key)
        if not product:
            stats["unmatched"] += 1
            continue
        stats["matched"] += 1
        variant = product.variant_override
        usd_price = _resolve_usd_for_variant(variant, variant_usd_map)
        if usd_price is None:
            stats["skipped"] += 1
            continue
        new_zar = to_zar(usd_price, rate)
        old_zar = getattr(product, "price_zar", None)
        if new_zar != old_zar:
            stats["updated"] += 1
            if not dry_run:
                product.price_zar = new_zar
                updates.append(product)
        else:
            stats["skipped"] += 1

    if updates and not dry_run:
        with transaction.atomic():
            PokemonProduct.objects.bulk_update(updates, ["price_zar"])

    return stats


class Command(BaseCommand):
    help = "Sync prices from TCGCSV → PokemonProduct.price_zar (USD × rate × 1.1, rounded up to R0.50)"

    def add_arguments(self, parser):
        parser.add_argument("--set-code", dest="set_code", default=None,
                            help="Sync one CardSet by code (e.g. BASE). Omit for all.")
        parser.add_argument("--rate", dest="rate", type=float, default=None,
                            help="Override USD→ZAR rate (default: live fetch).")
        parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=False,
                            help="Preview changes without writing to DB.")
        parser.add_argument("--delay", dest="delay", type=float, default=0.5,
                            help="Seconds between TCGCSV requests (default 0.5).")

    def handle(self, *args, **options):
        set_code = options["set_code"]
        dry_run = options["dry_run"]
        delay = options["delay"]

        if options["rate"]:
            rate = Decimal(str(options["rate"]))
            self.stdout.write(f"Override rate: R{rate}")
        else:
            self.stdout.write("Fetching live USD→ZAR rate…")
            rate = fetch_exchange_rate()
            self.stdout.write(self.style.SUCCESS(f"1 USD = R{rate}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes."))

        self.stdout.write("Fetching TCGCSV groups…")
        try:
            groups = fetch_tcgcsv_groups()
        except Exception as exc:
            raise CommandError(f"Failed: {exc}")
        self.stdout.write(f"  {len(groups)} groups found.")

        by_name = {}
        by_abbr = {}
        for g in groups:
            gid = g.get("groupId") or g.get("id")
            gname = (g.get("name") or "").strip()
            gabbr = (g.get("abbreviation") or "").strip().upper()
            if gname:
                by_name[gname.lower()] = gid
            if gabbr:
                by_abbr[gabbr] = gid

        if set_code:
            try:
                card_sets = [CardSet.objects.get(code=set_code.upper())]
            except CardSet.DoesNotExist:
                raise CommandError(f"CardSet '{set_code}' not found.")
        else:
            card_sets = list(CardSet.objects.all().order_by("release_date"))

        self.stdout.write(f"Syncing {len(card_sets)} set(s)…\n")
        totals = {"matched": 0, "updated": 0, "skipped": 0, "unmatched": 0}

        for card_set in card_sets:
            group_id = self._resolve_group_id(card_set, by_name, by_abbr)
            if group_id is None:
                self.stdout.write(self.style.WARNING(f"[{card_set.code}] No TCGCSV match — skipping."))
                continue

            self.stdout.write(f"[{card_set.code}] group={group_id} fetching prices…")
            try:
                group_prices = fetch_prices_for_group(group_id)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  Error: {exc} — skipping."))
                time.sleep(delay)
                continue

            self.stdout.write(f"  {len(group_prices)} price rows.")
            stats = sync_set_prices(card_set, group_prices, rate, dry_run,
                                    self.stdout, self.style)
            for k, v in stats.items():
                totals[k] += v
            self.stdout.write(self.style.SUCCESS(
                f"  matched={stats['matched']} updated={stats['updated']} "
                f"skipped={stats['skipped']} unmatched={stats['unmatched']}"
            ))
            time.sleep(delay)

        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(
            f"DONE  matched={totals['matched']}  updated={totals['updated']}  "
            f"skipped={totals['skipped']}  unmatched={totals['unmatched']}"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — nothing written."))

    def _resolve_group_id(self, card_set, by_name, by_abbr):
        name_lower = (card_set.name or "").strip().lower()
        code_upper = (card_set.code or "").strip().upper()
        if name_lower in by_name:
            return by_name[name_lower]
        if code_upper in by_abbr:
            return by_abbr[code_upper]
        for tcg_name, gid in by_name.items():
            if name_lower in tcg_name or tcg_name in name_lower:
                return gid
        return None
'''

dest = "products/management/commands/sync_prices.py"
with open(dest, "w", encoding="utf-8") as f:
    f.write(CONTENT)

print(f"Written: {dest}")
print()
print("Now run:")
print("  python manage.py sync_prices --dry-run --set-code BASE")
