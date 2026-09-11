# products/management/commands/sync_rarities_from_tcgcsv.py
#
# Michael, 2026-09-11: "We need to clean up Pitch black, using TCGCSV to
# get the correct rarities first, I need to get it right before we do the
# next step!" -- fetches a set's products LIVE from TCGCSV (not a local
# dump) and corrects PokemonProduct.rarity against TCGCSV's own Rarity
# extendedData field, the authoritative source.
#
# WHY THIS WAS NEEDED: diffing Pitch Black (PBL) against TCGCSV found two
# real problems, both confirmed with Michael before writing this command:
#
#   1. Mega Darkrai EX 120/084 was tagged "hyper_rare" but TCGCSV says
#      "Mega Hyper Rare" -- a plain one-row sync miss.
#
#   2. The bigger one, and exactly the "Lurantis EX exists twice" bug
#      Michael flagged: TCGCSV distinguishes "Double Rare" (a card's
#      normal-numbered ex print, e.g. Lurantis ex 004/084) from "Ultra
#      Rare" (that same Pokemon's separate full-art reprint beyond the
#      set's numbered total, e.g. Lurantis ex 096/084) -- two different
#      real-world rarities. RARITY_MAP (in rebuild_from_tcgcsv.py, and its
#      now-stale twin in sync_tcgcsv.py) collapsed BOTH onto "ultra_rare",
#      since PokemonProduct.RARITY_CHOICES had no "Double Rare" option.
#      Fixed at the root: added rarity choice "double_rare" to
#      PokemonProduct.RARITY_CHOICES (Michael's pick, over reusing an
#      existing bucket like holo_rare) and corrected RARITY_MAP in
#      rebuild_from_tcgcsv.py to point "Double Rare" at it. This command is
#      what actually rewrites the affected rows.
#
#      This hits 10 pairs in Pitch Black alone (Lurantis, Wailord, Mega
#      Zeraora, Mega Chandelure, Rampardos, Mega Darkrai, Morpeko, Mega
#      Excadrill, Mega Delphox, Mega Slowbro) and is very likely present in
#      every other MEG/SV-era set with ex cards -- scoped to --set PBL for
#      now per Michael's ask, but built generically (any set in
#      rebuild_from_tcgcsv.GROUP_CONFIG) so the same command can clean up
#      the rest later without rewriting it.
#
# MATCHING: prefers tcgcsv_product_id, then the TCGCSV id embedded in
# pb_id ("TCGCSV-<id>-<variant>"), then falls back to matching by
# card_number against TCGCSV's own Number field when exactly one TCGCSV
# product at that card_number exists -- this is what catches Pitch
# Black's 10 base ex cards, which were created by hand via Django admin
# (pb_id "PB-MEG-PBL-<pokedex>-HR-EX-<num>", generate_pb_id()'s own
# format) before ever being linked to a TCGCSV product. Backfills
# tcgcsv_product_id on those rows in --apply mode so future runs (and any
# other command that matches via that field) don't need the fallback.
#
# Does NOT touch pb_id, price, images, or anything else -- rarity (and,
# only for previously-unlinked rows, tcgcsv_product_id) only.
#
# Defaults to dry-run. Pass --apply to save.
#
# Usage:
#   python manage.py sync_rarities_from_tcgcsv                # dry run, PBL
#   python manage.py sync_rarities_from_tcgcsv --set PBL --apply
#   python manage.py sync_rarities_from_tcgcsv --set MEG       # any set in GROUP_CONFIG

import re

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.management.commands.rebuild_from_tcgcsv import GROUP_CONFIG, RARITY_MAP
from products.models import CardSet, PokemonProduct

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
TCGCSV_PID_RE = re.compile(r"TCGCSV-(\d+)")


def _ext(extended_data, field_name):
    for item in extended_data:
        if item.get("name") == field_name:
            return item.get("value", "")
    return ""


def _numerator(number_raw):
    if not number_raw:
        return None
    head = str(number_raw).split("/", 1)[0].strip()
    return int(head) if head.isdigit() else None


class Command(BaseCommand):
    help = "Correct PokemonProduct.rarity for one set against TCGCSV's own Rarity data, fetched live."

    def add_arguments(self, parser):
        parser.add_argument("--set", type=str, default="PBL", help="CardSet.code to sync. Default: PBL")
        parser.add_argument("--apply", action="store_true", default=False, help="Actually save changes. Without this, only prints what would change.")

    def handle(self, *args, **options):
        set_code = options["set"]
        apply_changes = options["apply"]

        try:
            card_set = CardSet.objects.get(code=set_code)
        except CardSet.DoesNotExist:
            raise CommandError(f"No CardSet found with code {set_code!r}")

        group_id = next((gid for gid, cfg in GROUP_CONFIG.items() if cfg[0] == set_code), None)
        if group_id is None:
            raise CommandError(f"{set_code!r} is not in rebuild_from_tcgcsv.GROUP_CONFIG -- don't know its TCGCSV groupId.")

        self.stdout.write(f"Fetching TCGCSV group {group_id} ({card_set.name}) ...")
        try:
            resp = requests.get(f"{TCGCSV_BASE}/{group_id}/products", headers=HEADERS, timeout=30)
            resp.raise_for_status()
            tcg_products = resp.json().get("results", [])
        except Exception as e:
            raise CommandError(f"Failed to fetch TCGCSV products for group {group_id}: {e}")

        # productId -> {rarity, number, numerator}
        tcg_by_id = {}
        # numerator -> [productId, ...] (to detect ambiguous fallback matches)
        tcg_by_numerator = {}
        for p in tcg_products:
            ext = p.get("extendedData", [])
            rarity_raw = _ext(ext, "Rarity")
            number_raw = _ext(ext, "Number")
            num = _numerator(number_raw)
            entry = {"rarity": rarity_raw, "number": number_raw, "numerator": num}
            tcg_by_id[p["productId"]] = entry
            if num is not None:
                tcg_by_numerator.setdefault(num, []).append(p["productId"])

        self.stdout.write(f"  {len(tcg_products)} TCGCSV products, {len(tcg_by_numerator)} distinct card numbers")

        products = list(PokemonProduct.objects.filter(card_set=card_set, is_active=True))

        changes = []
        unmapped_rarities = set()
        unmatched = []
        backfill_links = []  # (product, tcgcsv_product_id) for --apply

        for prod in products:
            tid = prod.tcgcsv_product_id
            matched_via = "tcgcsv_product_id"

            if tid is None:
                m = TCGCSV_PID_RE.search(prod.pb_id or "")
                if m:
                    tid = int(m.group(1))
                    matched_via = "pb_id"

            if tid is None and prod.card_number is not None:
                candidates = tcg_by_numerator.get(prod.card_number, [])
                if len(candidates) == 1:
                    tid = candidates[0]
                    matched_via = "card_number fallback"

            tcg = tcg_by_id.get(tid) if tid is not None else None
            if tcg is None:
                unmatched.append(prod)
                continue

            rarity_raw = tcg["rarity"]
            if rarity_raw == "Code Card" or not rarity_raw:
                continue  # not a real card slot -- leave alone

            expected = RARITY_MAP.get(rarity_raw)
            if expected is None:
                unmapped_rarities.add(rarity_raw)
                continue

            needs_link = matched_via == "card_number fallback" and prod.tcgcsv_product_id is None
            if prod.rarity != expected or needs_link:
                changes.append({
                    "product": prod,
                    "old": prod.rarity,
                    "new": expected,
                    "tcg_rarity": rarity_raw,
                    "matched_via": matched_via,
                    "needs_link": needs_link,
                    "tid": tid,
                })

        self.stdout.write("")
        if unmatched:
            self.stdout.write(self.style.WARNING(f"{len(unmatched)} active product(s) had no TCGCSV match (left untouched):"))
            for p in unmatched[:15]:
                self.stdout.write(f"  #{p.card_number} {p.name} ({p.pb_id})")
            if len(unmatched) > 15:
                self.stdout.write(f"  ... and {len(unmatched) - 15} more")
            self.stdout.write("")

        if unmapped_rarities:
            self.stdout.write(self.style.WARNING(f"TCGCSV rarity string(s) with no RARITY_MAP entry -- these rows were skipped: {sorted(unmapped_rarities)}"))
            self.stdout.write("")

        if not changes:
            self.stdout.write(self.style.SUCCESS(f"No rarity changes needed for {set_code} -- already matches TCGCSV."))
            return

        rarity_only = [c for c in changes if c["old"] != c["new"]]
        link_only = [c for c in changes if c["old"] == c["new"] and c["needs_link"]]

        if rarity_only:
            self.stdout.write(f"{len(rarity_only)} product(s) need a rarity fix:")
            for c in rarity_only:
                p = c["product"]
                self.stdout.write(
                    f"  #{p.card_number:<4} {p.name:<28} {c['old']:<20} -> {c['new']:<20} "
                    f"(TCGCSV: {c['tcg_rarity']}, matched via {c['matched_via']})"
                )
            self.stdout.write("")

        if link_only:
            self.stdout.write(f"{len(link_only)} product(s) already correct but will get tcgcsv_product_id backfilled (matched via card_number fallback):")
            for c in link_only:
                p = c["product"]
                self.stdout.write(f"  #{p.card_number:<4} {p.name:<28} -> tcgcsv_product_id={c['tid']}")
            self.stdout.write("")

        if not apply_changes:
            self.stdout.write(self.style.WARNING(f"Dry run -- {len(changes)} product(s) would change. Re-run with --apply to save."))
            return

        with transaction.atomic():
            to_update = []
            for c in changes:
                p = c["product"]
                p.rarity = c["new"]
                if c["needs_link"]:
                    p.tcgcsv_product_id = c["tid"]
                to_update.append(p)
            PokemonProduct.objects.bulk_update(to_update, ["rarity", "tcgcsv_product_id"])

        self.stdout.write(self.style.SUCCESS(f"\nApplied: updated {len(changes)} product(s) in {set_code}."))
