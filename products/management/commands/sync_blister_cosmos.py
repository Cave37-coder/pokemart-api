"""
sync_blister_cosmos -- add the Cosmos Holo blister promos to their real sets
(2026-10-27).

Michael: "look for the promo card that is supplied in the 2 and 3 pack
blister, there is a cosmos holo card normally, but they are not numbered as
Promos, they have the normal set number, but they aren't anywhere to be
found, they are part of the Grand Master sets and I have loads that I can
load and sell."

TCGplayer files these under their own group, "Blister Exclusives" (TCGCSV
group 2289 -- 144 cards on 2026-10-27, 115 of them Cosmos Holo), e.g.
"Zarude - 056/084 (Cosmos Holo)", "Eevee - 116/128 (30th Celebration)
(Cosmos Holo)". None were on the site.

Each one is added to its PARENT set (the set its number belongs to -- Zarude
056/084 -> Pitch Black) as an extra print with variant "CH" (Cosmos Holo),
sitting next to that card's N/H/RH rows, so it shows on the card's set page,
the checklists and Grand Master Set completion:
  * parent found by: same card name + same card number on the site, then
    confirmed against the parent set's own TCGCSV list (the printed
    denominator, e.g. "/084", must match) so a same-name card in another
    set can't be picked by mistake;
  * card info (HP, attacks, artist, Pokedex no., regulation mark, legality,
    types...) copied from the parent card, any gaps filled from TCGCSV;
  * own TCGCSV product id + price (the daily price sync keeps it priced),
    own Cosmos Holo image re-hosted on R2, stock 0.
Anything that can't be matched with certainty is listed for a manual look,
never guessed.

Usage:
    python manage.py sync_blister_cosmos --dry-run
    python manage.py sync_blister_cosmos
    python manage.py sync_blister_cosmos --groups 2289,1840   # + Deck Exclusives cosmos
    python manage.py sync_blister_cosmos --weekly-day mon    # cron: Mondays only
"""
import re
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import PokemonProduct
from products.management.commands.sync_tcgcsv import GROUP_CONFIG, _get_rate, _zar_price
from products import card_info as info

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA-BlisterSync/1.0 (enquiries@pokebulk.co.za)"}
DEFAULT_GROUPS = [2289]  # Blister Exclusives
VARIANT = "CH"
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
# Never treat these as a "parent" set for a blister card.
NON_PARENT = {"PRIZEPACK", "SVP", "MEP", "SMP", "WCD"} | {c for c in GROUP_CONFIG if c.startswith(("PR-", "MCD", "TK", "TT"))}
# Fields copied from the parent card onto the Cosmos Holo print.
COPY_FIELDS = [
    "name", "name_japanese", "flavour_text", "description", "rarity", "pokedex_number", "pokedex_number_2",
    "card_number", "number", "regulation_mark", "legal_standard", "legal_expanded", "legal_unlimited",
    "hp", "artist", "supertype", "card_subtypes", "weakness_type", "weakness_value", "resistance_type",
    "resistance_value", "retreat_cost", "ability_name", "ability_type", "ability_text", "ability_2_name",
    "ability_2_type", "ability_2_text", "attack_1_name", "attack_1_cost", "attack_1_damage", "attack_1_text",
    "attack_2_name", "attack_2_cost", "attack_2_damage", "attack_2_text", "attack_3_name", "attack_3_cost",
    "attack_3_damage", "attack_3_text", "stage", "evolves_from", "evolves_to", "rules_text",
]


def parse_blister_name(name, number_raw):
    """-> (base name, numerator int, denominator int|None)."""
    m = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", number_raw or "")
    num, den = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    if num is None:
        m = re.match(r"^\s*(\d+)", number_raw or "")
        num = int(m.group(1)) if m else None
    base = re.split(r"\s+-\s+", name, maxsplit=1)[0]
    base = re.sub(r"\s*\d+\s*/\s*\d+.*$", "", base)      # "Tepig 15/114 (Cosmos Holo)"
    base = re.sub(r"\s*[\(\[].*$", "", base).strip()       # trailing (...) / [...]
    return base, num, den


def norm_name(name):
    """'Eevee - 116/128' / 'Pikachu (14/30)' / 'Zarude' -> 'eevee' / 'pikachu' / 'zarude'."""
    n = re.sub(r"\s+-\s+\S*\d.*$", "", name or "")
    n = re.sub(r"\s*[\(\[].*$", "", n)
    return n.strip().lower()


def split_number(raw):
    m = re.match(r"^\s*[A-Za-z]*(\d+)\s*/\s*[A-Za-z]*(\d+)", raw or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


class Command(BaseCommand):
    help = "Add Blister Exclusive Cosmos Holo cards to their parent sets (variant CH)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--groups", default=",".join(map(str, DEFAULT_GROUPS)),
                            help="TCGCSV group ids to read (default 2289 = Blister Exclusives)")
        parser.add_argument("--include-non-cosmos", action="store_true",
                            help="Also report non-Cosmos cards in those groups (never auto-added)")
        parser.add_argument("--no-images", action="store_true")
        parser.add_argument("--weekly-day", choices=list(WEEKDAYS))
        parser.add_argument("--rate", type=float)

    def handle(self, *args, **o):
        if o["weekly_day"]:
            if datetime.now(ZoneInfo("Africa/Johannesburg")).weekday() != WEEKDAYS[o["weekly_day"]]:
                self.stdout.write(f"sync_blister_cosmos: not {o['weekly_day']} (SAST) -- skipping.")
                return
        dry = o["dry_run"]
        rate = _get_rate(o.get("rate"))
        self._group_cache = {}
        code_to_gid = {code: gid for code, (gid, _n, _e) in GROUP_CONFIG.items()}
        counts = defaultdict(int)
        unmatched = []

        for gid in [int(g) for g in o["groups"].split(",") if g.strip()]:
            products = self.group_products(gid)
            prices = {}
            for row in self.fetch(f"{TCGCSV_BASE}/{gid}/prices"):
                usd = row.get("marketPrice") or row.get("midPrice") or row.get("lowPrice")
                if usd and (row["productId"] not in prices or (row.get("subTypeName") or "").startswith("Holo")):
                    prices[row["productId"]] = usd
            self.stdout.write(f"Group {gid}: {len(products)} products{'  [DRY RUN]' if dry else ''}")

            for p in products:
                pid, name = p["productId"], (p.get("name") or "").strip()
                extd = p.get("extendedData") or []
                number_raw = info.ext(extd, "Number")
                if not number_raw:
                    continue
                if "cosmo" not in name.lower():
                    counts["non_cosmos"] += 1
                    if o["include_non_cosmos"]:
                        unmatched.append(f"(not cosmos, skipped) {name} [{number_raw}]")
                    continue
                counts["cosmos"] += 1

                existing = PokemonProduct.objects.filter(tcgcsv_product_id=pid, variant_override=VARIANT).first()
                if existing:
                    counts["already"] += 1
                    continue

                base, num, den = parse_blister_name(name, number_raw)
                parent, why = self.find_parent(base, num, den, code_to_gid)
                if parent is None:
                    counts["unmatched"] += 1
                    unmatched.append(f"{name} [{number_raw}] (TCGCSV {pid}): {why}")
                    continue
                dup = PokemonProduct.objects.filter(
                    card_set=parent.card_set, card_number=parent.card_number, name=parent.name,
                    variant_override=VARIANT, condition="NM").first()
                if dup:
                    # Same card already added from a different blister listing.
                    counts["already"] += 1
                    continue

                usd = prices.get(pid)
                zar = _zar_price(usd, rate) if usd else Decimal("1.50")
                counts["created"] += 1
                self.stdout.write(f"  {'WOULD ADD' if dry else 'ADD'}  {parent.card_set.code} #{parent.card_number:03d} "
                                  f"{parent.name} -> Cosmos Holo  R{zar}  (TCGCSV {pid})")
                if dry:
                    continue
                with transaction.atomic():
                    prod = PokemonProduct(
                        pb_id=f"TCGCSV-{pid}-{VARIANT}", tcgcsv_product_id=pid,
                        card_set=parent.card_set, category=parent.category,
                        variant_override=VARIANT,
                        variant_sort=PokemonProduct.VARIANT_SORT_ORDER.get(VARIANT, 9),
                        condition="NM", price=zar, stock=0, is_active=True,
                    )
                    for f in COPY_FIELDS:
                        setattr(prod, f, getattr(parent, f))
                    info.apply_fields(prod, info.card_fields(extd), only_blank=True)
                    prod.save()
                    if parent.pokemon_types.exists():
                        prod.pokemon_types.set(parent.pokemon_types.all())
                if not o["no_images"]:
                    self.set_image(prod, pid, parent)
                time.sleep(0.05)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            f"Cosmos cards read: {counts['cosmos']} | {'would add' if dry else 'added'}: {counts['created']} | "
            f"already on site: {counts['already']} | could not match: {counts['unmatched']} | "
            f"non-cosmos skipped: {counts['non_cosmos']}")
        if unmatched:
            self.stdout.write("\nNeeds a manual look:")
            for line in unmatched:
                self.stdout.write("  " + line)

    # ------------------------------------------------------------------
    def fetch(self, url):
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])

    def group_products(self, gid):
        if gid not in self._group_cache:
            try:
                self._group_cache[gid] = self.fetch(f"{TCGCSV_BASE}/{gid}/products")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  TCGCSV group {gid} fetch failed: {e}"))
                self._group_cache[gid] = []
            time.sleep(0.1)
        return self._group_cache[gid]

    def set_numbers(self, gid):
        """{(numerator, denominator)} printed in a set's own TCGCSV group."""
        out = set()
        for p in self.group_products(gid):
            n, d = split_number(info.ext(p.get("extendedData"), "Number"))
            if n is not None:
                out.add((n, d))
        return out

    def find_parent(self, base, num, den, code_to_gid):
        if not base or num is None:
            return None, "no usable name/number"
        qs = (PokemonProduct.objects.select_related("card_set", "category")
              .filter(condition="NM", card_number=num, name__iexact=base)
              .exclude(card_set__code__in=NON_PARENT).exclude(variant_override=VARIANT))
        rows = list(qs)
        if not rows:
            rows = [r for r in PokemonProduct.objects.select_related("card_set", "category")
                    .filter(condition="NM", card_number=num, name__istartswith=base)
                    .exclude(card_set__code__in=NON_PARENT).exclude(variant_override=VARIANT)
                    if norm_name(r.name) == base.lower()]
        if not rows:
            return None, f"no '{base}' #{num} on the site (parent set not loaded?)"
        by_set = defaultdict(list)
        for r in rows:
            by_set[r.card_set.code].append(r)
        confirmed = []
        for code, set_rows in by_set.items():
            gid = code_to_gid.get(code)
            if gid and den is not None:
                if (num, den) in self.set_numbers(gid):
                    confirmed.append(code)
            elif len(by_set) == 1 and (den is None or set_rows[0].card_set.total_cards in (0, den)):
                confirmed.append(code)  # only one candidate and nothing contradicts it
        if len(confirmed) != 1:
            return None, (f"{len(confirmed)} sets confirmed for #{num}/{den} "
                          f"(candidates: {', '.join(sorted(by_set))})")
        set_rows = by_set[confirmed[0]]
        order = {"H": 0, "N": 1, "RH": 2}
        set_rows.sort(key=lambda r: order.get(r.variant_override or "N", 9))
        return set_rows[0], ""

    def set_image(self, prod, pid, parent):
        for size in ("400w", "200w"):
            try:
                url = info.rehost_card_image(prod, info.tcgplayer_image(pid, size))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"    image failed for {prod.name} ({pid}): {e}"))
                url = ""
            if url:
                PokemonProduct.objects.filter(pk=prod.pk).update(image_url=url)
                return
        # No Cosmos image on TCGplayer: fall back to the parent's (R2) image.
        if parent.image_url:
            PokemonProduct.objects.filter(pk=prod.pk).update(image_url=parent.image_url)
