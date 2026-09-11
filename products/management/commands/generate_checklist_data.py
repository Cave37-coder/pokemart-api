# products/management/commands/generate_checklist_data.py
#
# Michael, 2026-09-11: "yes, build" -- regenerates the frontend's
# `checklistData.ts` (src/lib/checklistData.ts in pokemart-frontend)
# straight from this DB, closing the gap discovered this session: that
# file had no generator at all, was a one-off hand-built snapshot, and
# had drifted out of sync with the live DB in two ways -- a richer,
# TCGCSV-native rarity vocabulary (24 strings like "Double Rare",
# "Amazing Rare") that didn't map 1:1 onto this DB's own coarser
# `PokemonProduct.RARITY_CHOICES` (15 values), and, most recently, still
# listing Unseen Forces' Unown Collection inside UF after that was split
# into its own CardSet (UFUC) here.
#
# DESIGN: only ever rewrites the `SETS` blob. Every other export in
# checklistData.ts (ERA_COLORS, TIER_COLORS, TIER_LABELS_FE,
# MASTER_SET_CHASE_RARITIES, *_VARIANTS, TIER_VARIANT_SCOPE,
# TIER_NUMBERED_ONLY, ERA_ORDER) is hand-maintained tier/display config,
# not card data -- this command reads the file, replaces just the SETS
# assignment, and writes everything else back untouched, verbatim.
#
# RARITY DISPLAY: uses PokemonProduct.RARITY_CHOICES' own labels directly
# (dict(PokemonProduct.RARITY_CHOICES)) rather than trying to preserve the
# old TCGCSV-native strings. This is a deliberate, visible change --
# rarity labels on the checklist pages get coarser for some older cards
# (e.g. an "Amazing Rare" now displays as "Holo Rare", matching how
# rebuild_from_tcgcsv.py's RARITY_MAP already buckets it in this DB) --
# but it's the correct tradeoff: MASTER_SET_CHASE_RARITIES and every tier
# gate already only ever look at this same coarse backend vocabulary, so
# keeping the DISPLAY string honest to what's actually driving completion
# logic beats preserving decorative labels that no longer matched it.
#
# NUMBERING: display_num and the genuine-collision disambiguation
# (id-suffixed keys, e.g. "103/189-404513") deliberately mirror
# get_set_card_map() in products/completion.py exactly -- same fallback
# to zero-padded card_number/total_cards when `number` is blank, same
# two-pass variant_override-count collision detection. This is the same
# dedup logic that fixed the TT22 Mewtwo/Haunter bug; reimplementing it
# here (rather than importing it) because get_set_card_map() only returns
# {variants: set(), rarity}, not the per-variant name/price/TCGCSV-id this
# file also needs -- but the grouping/collision rules must stay identical
# or this file's card keys silently drift from what checklist_progress/
# checklist_toggle expect.
#
# PID: card.variants[].pid is NOT PokemonProduct.id -- per
# pokemart-frontend/src/app/checklists/page.tsx (see its own 2026-08-01
# bugfix comment), the checklist page re-fetches /api/products/?card_set=
# live on load and matches each variant by the numeric TCGCSV id embedded
# in PokemonProduct.pb_id (pattern "TCGCSV-(\d+)") to wire up Buy buttons
# and stock. So pid here must be that same number. Falls back to
# PokemonProduct.id for the (currently rare) rows whose pb_id doesn't
# follow that pattern -- functionally inert for Buy-button matching
# either way, since the frontend's own live-fetch regex won't match those
# rows either; this is a pre-existing gap in non-TCGCSV-synced rows, not
# something this command can fix from static data alone.
#
# Usage:
#   python manage.py generate_checklist_data
#   python manage.py generate_checklist_data --file "../pokemart-frontend/src/lib/checklistData.ts"

import json
import re
from collections import Counter, OrderedDict, defaultdict

from django.core.management.base import BaseCommand, CommandError

from products.models import CardSet, PokemonProduct

DEFAULT_FILE = "../pokemart-frontend/src/lib/checklistData.ts"

# CardSet.era.code -> the display label ERA_COLORS/ERA_ORDER in
# checklistData.ts already key on. Deliberately explicit and total (not a
# .get() with a fallback) -- a new era code showing up here unmapped
# means a brand new era was added to the catalog and needs a human
# decision on its display label/color/ERA_ORDER position, not a silent
# guess.
ERA_DISPLAY_MAP = {
    "WotC": "WotC Base",
    "WotCN": "WotC Neo",
    "WotCL": "WotC Legendary",
    "WotCO": "WotC Other",
    "EX": "EX Era",
    "DP": "Diamond & Pearl",
    "HGSS": "HG&SS",
    "BW": "Black & White",
    "XY": "XY Era",
    "SM": "Sun & Moon",
    "SWSH": "Sword & Shield",
    "SV": "Scarlet & Violet",
    "MEG": "Mega Evolution",
    "TOT": "Special - Trick or Trade",
    "PRIZE": "Special - Prize Pack",
    # 2026-09-11: a past rebuild_from_tcgcsv.py run created a handful of
    # promo/filler CardSets (Promos, POP series, McDonald's collections)
    # under a second, coarser era-code scheme (B1-B8) instead of the
    # fine-grained one above -- confirmed via generate_checklist_data's own
    # unmapped-era check, and cross-checked live: the main numbered
    # expansion sets (Neo Genesis, Evolutions, Prize Pack Series, Trick or
    # Trade, etc) all still carry the correct fine-grained codes, so this
    # only affects secondary sets. Mapped to the SAME display label as
    # their fine-grained sibling era, since it's the same real-world era
    # either way -- not attempting to fix the underlying Era FK split here.
    "B1": "WotC Base",
    "B2": "EX Era",
    "B3": "Diamond & Pearl",
    "B4": "Black & White",
    "B5": "XY Era",
    "B6": "Sun & Moon",
    "B7": "Sword & Shield",
    "B8": "Scarlet & Violet",
}

TCGCSV_PID_RE = re.compile(r"TCGCSV-(\d+)")

FULL_VARIANTS = frozenset({
    "N", "H", "RH", "PB", "MB", "LB", "FB", "QB", "UB", "DB", "TT", "ESH",
})


def fallback_display_num(card_number: int, total_cards: int) -> str:
    """Must match products/completion.py's _fallback_display_num exactly."""
    return f"{str(card_number).zfill(3)}/{total_cards}"


def build_set_cards(card_set: CardSet) -> list:
    """Returns a list of card dicts for this set's checklistData.ts entry,
    using the same display_num + collision-disambiguation rules as
    get_set_card_map() in products/completion.py (see module note above),
    extended to also carry name/rarity/pid/price per variant."""
    # See the matching 2026-09-11 fix + comment in get_set_card_map()
    # (products/completion.py) -- letter-numbered cards (Unown Collection
    # "A/28".."Z/28") have no integer card_number and must NOT be dropped
    # just because of that; only skip a row with neither a usable `number`
    # nor a card_number.
    products = (
        PokemonProduct.objects
        .filter(card_set=card_set, is_active=True)
        .values("id", "pb_id", "card_number", "variant_override", "number", "name", "rarity", "price")
    )
    total_cards = card_set.total_cards or 0

    rows_by_display_num = defaultdict(list)
    for p in products:
        variant = p["variant_override"] or "N"
        if variant not in FULL_VARIANTS:
            continue
        raw_number = (p["number"] or "").strip()
        if not raw_number and p["card_number"] is None:
            continue
        display_num = raw_number or fallback_display_num(p["card_number"], total_cards)
        rows_by_display_num[display_num].append((p, variant))

    entries = {}
    for display_num, rows in rows_by_display_num.items():
        variant_counts = Counter(v for _, v in rows)
        is_genuine_collision = any(c > 1 for c in variant_counts.values())

        if not is_genuine_collision:
            groups = {None: rows}
        else:
            groups = defaultdict(list)
            for p, variant in rows:
                groups[p["name"]].append((p, variant))

        for name_key, group_rows in groups.items():
            key = display_num if len(groups) == 1 else f"{display_num}-{min(p['id'] for p, _ in group_rows)}"
            entry = entries.setdefault(key, {
                "card_number": group_rows[0][0]["card_number"],
                "name": group_rows[0][0]["name"],
                "rarity": group_rows[0][0]["rarity"],
                "num": key,
                "variants": OrderedDict(),
            })
            for p, variant in group_rows:
                match = TCGCSV_PID_RE.search(p["pb_id"] or "")
                pid = int(match.group(1)) if match else p["id"]
                price = float(p["price"]) if p["price"] is not None else 0.0
                # If the same (display_num, variant) somehow has more than
                # one active row (shouldn't happen), keep the first seen
                # rather than flip-flopping on iteration order.
                entry["variants"].setdefault(variant, {"vc": variant, "pid": pid, "zar": price})

    rarity_display = dict(PokemonProduct.RARITY_CHOICES)

    cards = []
    for entry in entries.values():
        cards.append({
            "num": entry["num"],
            "name": entry["name"],
            "rarity": rarity_display.get(entry["rarity"], entry["rarity"]),
            "variants": list(entry["variants"].values()),
        })

    def sort_key(c):
        num = c["num"]
        card_number = None
        head = num.split("/", 1)[0].split("-", 1)[0]
        if head.isdigit():
            card_number = int(head)
        return (card_number if card_number is not None else 10**9, num)

    cards.sort(key=sort_key)
    return cards


class Command(BaseCommand):
    help = "Regenerate the SETS blob in pokemart-frontend's checklistData.ts from this DB. Leaves every other export (ERA_COLORS, TIER_*, *_VARIANTS, ERA_ORDER) untouched."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, default=DEFAULT_FILE, help=f"Path to checklistData.ts. Default: {DEFAULT_FILE}")

    def handle(self, *args, **options):
        file_path = options["file"]

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}\nRun this from pokemart-api's root, or pass --file with the full path to checklistData.ts.")

        m = re.search(r"export const SETS: Record<string, SetData> = (\{.*?\});\n", content, re.DOTALL)
        if not m:
            raise CommandError("Could not find 'export const SETS: Record<string, SetData> = {...};' in that file -- format may have changed.")

        card_sets = (
            CardSet.objects
            .select_related("era")
            .filter(products__is_active=True)
            .distinct()
            .order_by("code")
        )

        new_sets = OrderedDict()
        unmapped_eras = set()
        total_cards = 0

        for card_set in card_sets:
            era_code = card_set.era.code if card_set.era else None
            if era_code not in ERA_DISPLAY_MAP:
                unmapped_eras.add((era_code, card_set.era.name if card_set.era else "(no era)"))
                continue

            cards = build_set_cards(card_set)
            if not cards:
                continue

            new_sets[card_set.code] = {
                "name": card_set.name,
                "era": ERA_DISPLAY_MAP[era_code],
                "cards": cards,
            }
            total_cards += len(cards)

        if unmapped_eras:
            raise CommandError(
                "Found CardSet(s) with an era code not in ERA_DISPLAY_MAP -- "
                "add it there (and to ERA_COLORS/ERA_ORDER in checklistData.ts) "
                f"before regenerating: {sorted(unmapped_eras)}"
            )

        new_blob = json.dumps(new_sets, separators=(",", ":"), ensure_ascii=False)
        new_content = content[:m.start(1)] + new_blob + content[m.end(1):]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        self.stdout.write(self.style.SUCCESS(
            f"Wrote {file_path}\n"
            f"  Sets:  {len(new_sets)}\n"
            f"  Cards: {total_cards}"
        ))
