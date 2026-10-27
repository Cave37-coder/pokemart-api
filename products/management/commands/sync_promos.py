"""
sync_promos -- weekly promo-card sync from TCGCSV (2026-10-27).

Michael: "I need a weekly update on all Promo sets, where we pull all new
cards from TCGCSV with all relevant info for the card too! We are missing
at least 20 cards that I know of." (A live check on 2026-10-27 found 59
missing from Mega Evolution Promos alone, plus 2 SVP and 1 SM promo.)

For every promo set (Black Star promos, SVP, MEP, McDonald's):
  * NEW cards on TCGCSV that aren't on the site are created -- name,
    number, rarity, price (USD x rate x 1.10, R0.50 up, min R1.50), image
    re-hosted on R2, and the card info TCGCSV carries: energy type, HP,
    stage, card text / ability, attacks (with energy cost + damage),
    weakness, resistance, retreat.
  * Cards ALREADY on the site get any BLANK info fields filled in from
    TCGCSV (never overwrites Serebii/Bulbapedia data) and a missing/
    external image re-hosted on R2.
  * Older promo sets that were loaded from another source (rows without a
    TCGCSV product id) are matched by number + name instead. A single,
    unambiguous match gets linked (tcgcsv_product_id set, so the daily
    price sync starts pricing it); anything ambiguous or missing is only
    REPORTED, never created, so nothing gets duplicated. Use
    --create-legacy to create the missing ones in those sets anyway.

Prices for existing cards are left to the daily sync_prices_only run.

Usage:
    python manage.py sync_promos --dry-run            # show what would change
    python manage.py sync_promos                       # all promo sets
    python manage.py sync_promos --set-code MEP        # one set
    python manage.py sync_promos --weekly-day mon --email   # cron: Mondays only, email a summary
"""
import re
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import PokemonProduct, CardSet, Category
from products.management.commands.sync_tcgcsv import (
    GROUP_CONFIG, RARITY_MAP, SUBTYPE_MAP, _get_rate, _zar_price, _parse_number,
)
from products import card_info as info

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA-PromoSync/1.0 (enquiries@pokebulk.co.za)"}
SUMMARY_TO = ["enquiries@pokebulk.co.za"]
# A set counts as "TCGCSV-keyed" (safe to create missing cards by product id)
# when at least this share of its rows already carry a TCGCSV product id.
KEYED_SHARE = 0.8

# Group 1861 is stored on the site as "SMP" (333 rows), not GROUP_CONFIG's
# "PR-SM" (a handful of stray rows) -- use the real code.
CODE_OVERRIDES = {"PR-SM": "SMP"}
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def promo_sets():
    out = []
    for code, (gid, name, _era) in GROUP_CONFIG.items():
        if code.startswith("PR-") or code.startswith("MCD") or code in ("SVP", "MEP"):
            out.append((CODE_OVERRIDES.get(code, code), gid, name))
    return out


def base_name(name):
    """'Chespin - XY01' -> 'chespin'; 'Murkrow - 021 (Prerelease) [Staff]' ->
    'murkrow (prerelease) [staff]'. Keeps qualifiers, drops the number token."""
    n = re.sub(r"\s+-\s+[A-Za-z]{0,6}\s?\d+[a-z]?(?=\s|$)", "", name or "")
    return re.sub(r"\s+", " ", n).strip().lower()


def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


class Command(BaseCommand):
    help = "Weekly: pull new promo cards (with full card info) from TCGCSV."

    def add_arguments(self, parser):
        parser.add_argument("--set-code", help="Only this promo set (e.g. MEP, SVP)")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--create-legacy", action="store_true",
                            help="Also create missing cards in sets not keyed by TCGCSV id")
        parser.add_argument("--no-images", action="store_true", help="Skip R2 image re-hosting")
        parser.add_argument("--weekly-day", choices=list(WEEKDAYS),
                            help="Only run on this weekday (SAST) -- for the daily cron")
        parser.add_argument("--email", action="store_true", help="Email a summary to enquiries@ when anything changed")
        parser.add_argument("--rate", type=float)

    def handle(self, *args, **o):
        if o["weekly_day"]:
            today = datetime.now(ZoneInfo("Africa/Johannesburg")).weekday()
            if today != WEEKDAYS[o["weekly_day"]]:
                self.stdout.write(f"sync_promos: not {o['weekly_day']} (SAST) -- skipping.")
                return
        dry = o["dry_run"]
        sets = promo_sets()
        if o["set_code"]:
            sets = [s for s in sets if s[0] == o["set_code"]]
            if not sets:
                raise CommandError(f"Unknown promo set code {o['set_code']}. Known: {', '.join(c for c, _, _ in promo_sets())}")
        rate = _get_rate(o.get("rate"))
        self.stdout.write(f"1 USD = R{rate:.2f}  |  {len(sets)} promo set(s){'  [DRY RUN]' if dry else ''}\n")
        category, _ = Category.objects.get_or_create(name="Pokemon")

        report = []          # lines for the email / end summary
        totals = defaultdict(int)
        for code, gid, sname in sets:
            card_set = CardSet.objects.filter(code=code).first()
            if card_set is None:
                self.stdout.write(self.style.WARNING(f"[{code}] no CardSet on the site -- skipped"))
                continue
            try:
                products = get_json(f"{TCGCSV_BASE}/{gid}/products")
                price_rows = get_json(f"{TCGCSV_BASE}/{gid}/prices")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{code}] TCGCSV fetch failed: {e}"))
                continue
            stats = self.sync_set(code, card_set, category, products, price_rows, rate, dry, o)
            for k, v in stats["counts"].items():
                totals[k] += v
            c = stats["counts"]
            self.stdout.write(
                f"[{code}] {sname}: tcgcsv cards {c['tcgcsv_cards']}, created {c['created']}, "
                f"info filled {c['filled']}, linked {c['linked']}, images {c['images']}, "
                f"missing (report only) {c['missing_report']}, ambiguous {c['ambiguous']}")
            report += stats["lines"]
            time.sleep(0.2)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            f"DONE{' (dry run)' if dry else ''}: created {totals['created']}, filled {totals['filled']}, "
            f"linked {totals['linked']}, images {totals['images']}, still missing (report only) "
            f"{totals['missing_report']}, ambiguous {totals['ambiguous']}")
        for line in report:
            self.stdout.write("  " + line)

        if o["email"] and not dry and (totals["created"] or totals["missing_report"] or totals["linked"]):
            self.send_summary(totals, report)

    # ------------------------------------------------------------------
    def sync_set(self, code, card_set, category, products, price_rows, rate, dry, o):
        counts = defaultdict(int)
        lines = []
        prices = defaultdict(dict)  # pid -> {subtype: usd}
        for row in price_rows:
            usd = row.get("marketPrice") or row.get("midPrice") or row.get("lowPrice")
            prices[row["productId"]][row.get("subTypeName") or ""] = usd

        rows = list(PokemonProduct.objects.filter(card_set=card_set, condition="NM"))
        keyed = [r for r in rows if r.tcgcsv_product_id]
        is_keyed = bool(rows) and len(keyed) / len(rows) >= KEYED_SHARE or not rows
        by_pid = defaultdict(list)
        for r in keyed:
            by_pid[r.tcgcsv_product_id].append(r)
        unkeyed = defaultdict(list)  # (card_number, base name) -> rows without tcgcsv id
        for r in rows:
            if not r.tcgcsv_product_id:
                unkeyed[(r.card_number, base_name(r.name))].append(r)
        all_pb_ids = set(PokemonProduct.objects.filter(pb_id__startswith="TCGCSV-").values_list("pb_id", flat=True))

        cards = [p for p in products if info.ext(p.get("extendedData"), "Number") or info.ext(p.get("extendedData"), "Rarity")]
        counts["tcgcsv_cards"] = len(cards)
        # How many TCGCSV cards share a (number, base name) -- only unique ones get legacy-linked.
        tcg_key_count = defaultdict(int)
        for p in cards:
            tcg_key_count[(_parse_number(info.ext(p["extendedData"], "Number")), base_name(p["name"]))] += 1

        for p in cards:
            pid = p["productId"]
            name = (p.get("name") or "").strip()
            extd = p.get("extendedData") or []
            number_raw = info.ext(extd, "Number")
            rarity_raw = info.ext(extd, "Rarity")
            card_number = _parse_number(number_raw)
            fields = info.card_fields(extd)
            variants = prices.get(pid) or {"": None}

            # 1) already on the site by product id -> fill blanks / image
            if pid in by_pid:
                for row in by_pid[pid]:
                    self.fill_existing(row, fields, p, dry, o, counts)
                continue

            # 2) legacy rows (other source): unique number + name match -> link
            key = (card_number, base_name(name))
            cands = unkeyed.get(key, [])
            if cands:
                # One TCGCSV card for this number+name: every site row with
                # it is a print (N/H/RH) of that same card -- link them all
                # (one product id across variants is normal on TCGCSV).
                if tcg_key_count[key] == 1:
                    counts["linked"] += 1
                    lines.append(f"{code} LINK  {cands[0].name} #{number_raw} "
                                 f"({'/'.join(sorted(r.variant_override or 'N' for r in cands))}) -> TCGCSV {pid}")
                    for row in cands:
                        if not dry:
                            row.tcgcsv_product_id = pid
                            row.save(update_fields=["tcgcsv_product_id", "updated_at"])
                        self.fill_existing(row, fields, p, dry, o, counts)
                    unkeyed.pop(key, None)
                else:
                    counts["ambiguous"] += 1
                    lines.append(f"{code} CHECK {name} #{number_raw}: {len(cands)} site rows / "
                                 f"{tcg_key_count[key]} TCGCSV cards share this number+name")
                continue

            # 3) genuinely missing
            if not is_keyed and not o["create_legacy"]:
                counts["missing_report"] += 1
                lines.append(f"{code} MISSING {name} #{number_raw} (TCGCSV {pid}) -- legacy set, not auto-created")
                continue
            for sub, usd in variants.items():
                variant = SUBTYPE_MAP.get(sub, "N")
                pb_id = f"TCGCSV-{pid}-{variant}"
                if pb_id in all_pb_ids or f"TCGCSV-{pid}" in all_pb_ids:
                    continue
                zar = _zar_price(usd, rate) if usd else Decimal("1.50")
                counts["created"] += 1
                lines.append(f"{code} NEW   {name} #{number_raw} {variant} R{zar}")
                if dry:
                    continue
                with transaction.atomic():
                    prod = PokemonProduct(
                        pb_id=pb_id, tcgcsv_product_id=pid, name=name,
                        card_number=card_number,
                        number=(number_raw or "") if card_number is None else "",
                        card_set=card_set, category=category,
                        variant_override=variant,
                        variant_sort=PokemonProduct.VARIANT_SORT_ORDER.get(variant, 9),
                        rarity=RARITY_MAP.get(rarity_raw, "common"),
                        price=zar, stock=0, is_active=True,
                    )
                    info.apply_fields(prod, fields, only_blank=True)
                    prod.save()
                    all_pb_ids.add(pb_id)
                    info.set_types(prod, fields.get("_card_type"))
                if not o["no_images"]:
                    self.set_image(prod, pid, counts)
        return {"counts": counts, "lines": lines}

    def fill_existing(self, row, fields, product_json, dry, o, counts):
        changed = info.apply_fields(row, fields, only_blank=True)
        if changed:
            counts["filled"] += 1
            if not dry:
                row.save(update_fields=changed + ["updated_at"])
                info.set_types(row, fields.get("_card_type"))
        from products.admin import R2_CDN
        if not o["no_images"] and not (row.image_url or "").startswith(R2_CDN):
            if dry:
                counts["images"] += 1
            else:
                self.set_image(row, row.tcgcsv_product_id or product_json["productId"], counts)

    def set_image(self, prod, pid, counts):
        for size in ("400w", "200w"):
            try:
                url = info.rehost_card_image(prod, info.tcgplayer_image(pid, size))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"    image failed for {prod.name} ({pid}): {e}"))
                return
            if url:
                PokemonProduct.objects.filter(pk=prod.pk).update(image_url=url)
                counts["images"] += 1
                return

    def send_summary(self, totals, lines):
        from django.core.mail import EmailMessage
        body = (
            f"Weekly promo sync ({datetime.now(ZoneInfo('Africa/Johannesburg')):%d %b %Y})\n\n"
            f"New cards added: {totals['created']}\n"
            f"Existing cards linked to TCGCSV: {totals['linked']}\n"
            f"Card info filled in: {totals['filled']}\n"
            f"Missing in older promo sets (not auto-added, check these): {totals['missing_report']}\n"
            f"Ambiguous number/name matches: {totals['ambiguous']}\n\n"
            "New cards are added with stock 0 -- load stock in Stock Entry.\n\n" + "\n".join(lines[:400])
        )
        try:
            EmailMessage(subject=f"PokeBulk promo sync: {totals['created']} new card(s)", body=body, to=SUMMARY_TO).send()
            self.stdout.write("Summary emailed.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Summary email failed: {e}"))
