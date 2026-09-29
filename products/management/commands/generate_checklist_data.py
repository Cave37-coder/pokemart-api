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
# DESIGN: rewrites both the `SETS` blob and the `SET_INDEX` blob (added
# 2026-09-29, see note below). Every OTHER export in checklistData.ts
# (ERA_COLORS, TIER_COLORS, TIER_LABELS_FE, MASTER_SET_CHASE_RARITIES,
# *_VARIANTS, TIER_VARIANT_SCOPE, TIER_NUMBERED_ONLY, ERA_ORDER) is still
# hand-maintained tier/display config, not card data -- untouched.
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
# SET_INDEX (added 2026-09-29): the /checklists/[era] browse-by-era page
# (pokemart-frontend/src/app/checklists/[era]/page.tsx) reads a SEPARATE
# export, SET_INDEX, to list a set's logo tile + "{code} - {cards} cards"
# meta line + progress bar, and links each tile to
# `/checklists?set=${s.code}` -- but SET_INDEX had been a one-off
# hand-typed array since the 09-16 drill-down page shipped, never
# regenerated alongside SETS. Michael, 2026-09-29: "I can't select any
# checklist from screenshot, it takes me back to Era page!!!!" on the
# Sword & Shield era page turned out to be exactly this drift: SET_INDEX
# listed the 12 mainline SWSH sets under fake marketing codes ("SWSH01"
# .."SWSH12") that are not real CardSet.code values (those are "SSH",
# "RCL", "DAA", "VIV", "BST", "CRE", "EVS", "FST", "BRS", "ASR", "LOR",
# "SIT") -- so `/checklists?set=SWSH10` found nothing in SETS and the
# page bounced back. Separately, 43 real, active sets (McDonald's
# collections, POP series, era-specific Black Star Promos, Trick or Trade
# TK22/23/24, Detective Pikachu, etc.) were simply never in SET_INDEX at
# all and could never be browsed to.
#
# Fixed at the root: SET_INDEX is now generated from the exact same
# `card_sets`/`cards` this command already computes for SETS, so its
# `code` is always a real, live SETS key and it always covers every set
# SETS does -- this class of drift can't recur. `cards`/`variants`/
# `set_zar` are recomputed from the live card list every run (note:
# getProgress/getSetValue in checklistShared.ts already read live from
# SETS[code] directly and were NEVER affected by SET_INDEX's stale
# numbers -- SET_INDEX only ever fed the cosmetic "{cards} cards" label
# and the pre-live-fetch set_zar fallback shown for an instant before
# ensureLivePrices() resolves). `name` keeps the existing hand-typed
# display string (with its "SWSH10:", "SM -", "XY -", "ME01:", "SV:"-style
# marketing prefixes) for every set that already had one in SET_INDEX --
# via NAME_OVERRIDES below, a one-time snapshot of the pre-fix SET_INDEX
# keyed by each set's REAL code -- and falls back to the DB's own
# card_set.name for the 43 sets that were never listed before, which
# don't have an established prefix convention to preserve.
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

# One-time snapshot (2026-09-29) of the pre-fix, hand-typed SET_INDEX's
# {code: name} pairs, keyed by each set's REAL CardSet.code -- for the 12
# mainline SWSH sets this means the key changed (was keyed by the fake
# "SWSH01".."SWSH12" codes; now keyed by "SSH".."SIT" etc, see the module
# note above) while the display text itself is untouched. Every set NOT in
# this map (the 43 that were missing from SET_INDEX entirely, plus any
# brand new set added after this snapshot) falls back to card_set.name
# as-is with no marketing prefix -- see build_set_index().
NAME_OVERRIDES = {
    '30C': '30th Celebration',
    '30CC': '30th Celebration: Classic Collection',
    'PBL': 'Pitch Black',
    'AOR': 'XY - Ancient Origins',
    'AQ': 'Aquapolis',
    'AR': 'Arceus',
    'ASC': 'ME: Ascended Heroes',
    'ASRTG': 'SWSH10: Astral Radiance Trainer Gallery',
    'BCR': 'Boundaries Crossed',
    'BKP': 'XY - BREAKpoint',
    'BKT': 'XY - BREAKthrough',
    'BLK': 'SV: Black Bolt',
    'BLW': 'Black and White',
    'BRSTG': 'SWSH09: Brilliant Stars Trainer Gallery',
    'BS': 'Base Set',
    'BS2': 'Base Set 2',
    'BSS': 'Base Set (Shadowless)',
    'CCC': 'Celebrations: Classic Collection',
    'CES': 'SM - Celestial Storm',
    'CG': 'Crystal Guardians',
    'CHP': "Champion's Path",
    'CLB': 'Celebrations',
    'CRI': 'ME04: Chaos Rising',
    'CRZ': 'SWSH: Crown Zenith',
    'CRZGG': 'SWSH: Crown Zenith: Galarian Gallery',
    'CoL': 'Call of Legends',
    'DCR': 'Double Crisis',
    'DEX': 'Dark Explorers',
    'DF': 'Dragon Frontiers',
    'DP': 'Diamond and Pearl',
    'DR': 'Dragon',
    'DRI': 'SV10: Destined Rivals',
    'DRM': 'Dragon Majesty',
    'DRV': 'Dragon Vault',
    'DRX': 'Dragons Exalted',
    'DS': 'Delta Species',
    'DX': 'Deoxys',
    'EM': 'Emerald',
    'EPO': 'Emerging Powers',
    'EVO': 'XY - Evolutions',
    'EX': 'Expedition',
    'FCO': 'XY - Fates Collide',
    'FFI': 'XY - Furious Fists',
    'FLF': 'XY - Flashfire',
    'FO': 'Fossil',
    'G1': 'Gym Heroes',
    'G2': 'Gym Challenge',
    'GE': 'Great Encounters',
    'GEN': 'Generations',
    'HIF': 'Hidden Fates',
    'HIFSV': 'Hidden Fates: Shiny Vault',
    'HL': 'Hidden Legends',
    'HP': 'Holon Phantoms',
    'HS': 'HeartGold SoulSilver',
    'JTG': 'SV09: Journey Together',
    'JU': 'Jungle',
    'KSS': 'Kalos Starter Set',
    'LA': 'Legends Awakened',
    'LC': 'Legendary Collection',
    'LM': 'Legend Maker',
    'LORTG': 'SWSH11: Lost Origin Trainer Gallery',
    'LTR': 'Legendary Treasures',
    'MA': 'Team Magma vs Team Aqua',
    'MD': 'Majestic Dawn',
    'MEE': 'MEE: Mega Evolution Energies',
    'MEG': 'ME01: Mega Evolution',
    'MEP': 'ME: Mega Evolution Promo',
    'MEW': 'SV: Scarlet & Violet 151',
    'MT': 'Mysterious Treasures',
    'N1': 'Neo Genesis',
    'N2': 'Neo Discovery',
    'N3': 'Neo Revelation',
    'N4': 'Neo Destiny',
    'NVI': 'Noble Victories',
    'NXD': 'Next Destinies',
    'OBF': 'SV03: Obsidian Flames',
    'PAF': 'SV: Paldean Fates',
    'PAL': 'SV02: Paldea Evolved',
    'PAR': 'SV04: Paradox Rift',
    'PFL': 'ME02: Phantasmal Flames',
    'PGO': 'Pokemon GO',
    'PHF': 'XY - Phantom Forces',
    'PK': 'Power Keepers',
    'PL': 'Platinum',
    'PLB': 'Plasma Blast',
    'PLF': 'Plasma Freeze',
    'PLS': 'Plasma Storm',
    'POR': 'ME03: Perfect Order',
    'PRC': 'XY - Primal Clash',
    'PRE': 'SV: Prismatic Evolutions',
    'PRIZEPACK': 'Prize Pack Series Cards',
    'RG': 'FireRed & LeafGreen',
    'ROS': 'XY - Roaring Skies',
    'RR': 'Rising Rivals',
    'RS': 'Ruby and Sapphire',
    'SCR': 'SV07: Stellar Crown',
    'SF': 'Stormfront',
    'SFA': 'SV: Shrouded Fable',
    'SHF': 'Shining Fates',
    'SHFSV': 'Shining Fates: Shiny Vault',
    'SHL': 'Shining Legends',
    'SI1': 'Southern Islands',
    'SITTG': 'SWSH12: Silver Tempest Trainer Gallery',
    'SK': 'Skyridge',
    'SM01': 'SM Base Set',
    'SM02': 'SM - Guardians Rising',
    'SM03': 'SM - Burning Shadows',
    'SM04': 'SM - Crimson Invasion',
    'SM05': 'SM - Ultra Prism',
    'SM06': 'SM - Forbidden Light',
    'SM10': 'SM - Unbroken Bonds',
    'SM11': 'SM - Unified Minds',
    'SM12': 'SM - Cosmic Eclipse',
    'SM8': 'SM - Lost Thunder',
    'SM9': 'SM - Team Up',
    'SMP': 'SM Promos',
    'SS': 'Sandstorm',
    'SSP': 'SV08: Surging Sparks',
    'STS': 'XY - Steam Siege',
    'SV': 'Supreme Victors',
    'SVE': 'SVE: Scarlet & Violet Energies',
    'SVI': 'SV01: Scarlet & Violet Base Set',
    'SVP': 'SV: Scarlet & Violet Promo Cards',
    'SW': 'Secret Wonders',
    'SSH': 'SWSH01: Sword & Shield Base Set',
    'RCL': 'SWSH02: Rebel Clash',
    'DAA': 'SWSH03: Darkness Ablaze',
    'VIV': 'SWSH04: Vivid Voltage',
    'BST': 'SWSH05: Battle Styles',
    'CRE': 'SWSH06: Chilling Reign',
    'EVS': 'SWSH07: Evolving Skies',
    'FST': 'SWSH08: Fusion Strike',
    'BRS': 'SWSH09: Brilliant Stars',
    'ASR': 'SWSH10: Astral Radiance',
    'LOR': 'SWSH11: Lost Origin',
    'SIT': 'SWSH12: Silver Tempest',
    'TEF': 'SV05: Temporal Forces',
    'TT22': 'Trick or Trade 2022',
    'TT23': 'Trick or Trade 2023',
    'TT24': 'Trick or Trade 2024',
    'TM': 'Triumphant',
    'TR': 'Team Rocket',
    'TRR': 'Team Rocket Returns',
    'TWM': 'SV06: Twilight Masquerade',
    'UD': 'Undaunted',
    'UF': 'Unseen Forces',
    'UL': 'Unleashed',
    'WHT': 'SV: White Flare',
    'XY': 'XY Base Set',
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
    #
    # 2026-09-29, Michael: "Sword & Shield sets are disaster... the holo and
    # Rev holo's don't link together on most sets too!" -- half of that (a
    # card correctly getting ONE merged entry, but its N/H button showing
    # AFTER its RH button) traced to THIS query having no .order_by() at
    # all. .values() doesn't clear Django's default ordering, so it was
    # silently inheriting PokemonProduct.Meta.ordering = ["-created_at"] --
    # i.e. whichever variant row was synced/touched MOST RECENTLY came back
    # FIRST, and entry["variants"] below is an OrderedDict that keeps
    # insertion order, so that same accident-of-sync-timing order is exactly
    # what got baked into checklistData.ts's per-card variant list and
    # rendered as the button order on the checklist page (see
    # pokemart-frontend/src/app/checklists/page.tsx, which just does
    # card.variants.map(...) -- no re-sorting of its own). Ordering
    # explicitly by variant_sort makes N/H always land in the dict before
    # RH regardless of which row happened to sync last.
    products = (
        PokemonProduct.objects
        .filter(card_set=card_set, is_active=True)
        .order_by("variant_sort")
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


def build_set_index_entry(card_set: CardSet, era_label: str, cards: list) -> dict:
    """The browse-by-era page's SetMeta shape -- see the module-level note
    above for why this now exists and is regenerated every run instead of
    being hand-maintained. `code` is always card_set.code (a real, live
    SETS key), so a tile's `/checklists?set=${code}` link can never point
    at a set that doesn't exist."""
    variants_count = sum(len(c["variants"]) for c in cards)
    set_zar = round(sum(v["zar"] for c in cards for v in c["variants"]), 1)
    return {
        "code": card_set.code,
        "name": NAME_OVERRIDES.get(card_set.code, card_set.name),
        "era": era_label,
        "cards": len(cards),
        "variants": variants_count,
        "set_zar": set_zar,
    }


class Command(BaseCommand):
    help = "Regenerate the SETS and SET_INDEX blobs in pokemart-frontend's checklistData.ts from this DB. Leaves every other export (ERA_COLORS, TIER_*, *_VARIANTS, ERA_ORDER) untouched."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, default=DEFAULT_FILE, help=f"Path to checklistData.ts. Default: {DEFAULT_FILE}")

    def handle(self, *args, **options):
        file_path = options["file"]

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}\nRun this from pokemart-api's root, or pass --file with the full path to checklistData.ts.")

        m_sets = re.search(r"export const SETS: Record<string, SetData> = (\{.*?\});\n", content, re.DOTALL)
        if not m_sets:
            raise CommandError("Could not find 'export const SETS: Record<string, SetData> = {...};' in that file -- format may have changed.")

        m_index = re.search(r"export const SET_INDEX: SetMeta\[\] = (\[.*?\]);\n", content, re.DOTALL)
        if not m_index:
            raise CommandError("Could not find 'export const SET_INDEX: SetMeta[] = [...];' in that file -- format may have changed.")

        card_sets = (
            CardSet.objects
            .select_related("era")
            .filter(products__is_active=True)
            .distinct()
            .order_by("code")
        )

        old_index_codes = {e["code"] for e in json.loads(m_index.group(1))}

        new_sets = OrderedDict()
        new_index = []
        unmapped_eras = set()
        total_cards = 0
        new_to_index = []  # codes that weren't in the old SET_INDEX at all, for the summary

        for card_set in card_sets:
            era_code = card_set.era.code if card_set.era else None
            if era_code not in ERA_DISPLAY_MAP:
                unmapped_eras.add((era_code, card_set.era.name if card_set.era else "(no era)"))
                continue

            cards = build_set_cards(card_set)
            if not cards:
                continue

            era_label = ERA_DISPLAY_MAP[era_code]
            new_sets[card_set.code] = {
                "name": card_set.name,
                "era": era_label,
                "cards": cards,
            }
            total_cards += len(cards)

            new_index.append(build_set_index_entry(card_set, era_label, cards))
            if card_set.code not in old_index_codes:
                new_to_index.append(card_set.code)

        if unmapped_eras:
            raise CommandError(
                "Found CardSet(s) with an era code not in ERA_DISPLAY_MAP -- "
                "add it there (and to ERA_COLORS/ERA_ORDER in checklistData.ts) "
                f"before regenerating: {sorted(unmapped_eras)}"
            )

        new_sets_blob = json.dumps(new_sets, separators=(",", ":"), ensure_ascii=False)
        new_index_blob = json.dumps(new_index, separators=(",", ":"), ensure_ascii=False)

        # Replace SET_INDEX first if it comes later in the file, else SETS
        # first -- either order is fine since we use each match's own
        # stored span, just don't let editing one invalidate the other's
        # offsets. Safest: always replace the later span first.
        if m_index.start(1) > m_sets.start(1):
            new_content = content[:m_index.start(1)] + new_index_blob + content[m_index.end(1):]
            new_content = new_content[:m_sets.start(1)] + new_sets_blob + new_content[m_sets.end(1):]
        else:
            new_content = content[:m_sets.start(1)] + new_sets_blob + content[m_sets.end(1):]
            new_content = new_content[:m_index.start(1)] + new_index_blob + new_content[m_index.end(1):]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        self.stdout.write(self.style.SUCCESS(
            f"Wrote {file_path}\n"
            f"  Sets:  {len(new_sets)}\n"
            f"  Cards: {total_cards}\n"
            f"  SET_INDEX entries: {len(new_index)}"
        ))
        if new_to_index:
            self.stdout.write(
                f"  Newly added to SET_INDEX (previously unreachable on the browse-by-era page): "
                f"{', '.join(sorted(new_to_index))}"
            )
