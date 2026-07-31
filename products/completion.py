# pokemart-api: products/completion.py
#
# Collection-completion tier calculations for Checklists Phase 1
# ("Compare & Compete" -- leaderboards + Wall of Honour). Designed and
# confirmed with Michael, 2026-07-30.
#
# ── The ladder ──────────────────────────────────────────────────────────────
# Most sets get 4 tiers (a 5th, Grand Master, is deferred -- needs promo-card
# research per set, same as the Prize Pack sourcing effort):
#
#   1. Broke Base       - numbered cards only (card_number <= total_cards).
#                          At least one of {N, H} checked per card (whichever
#                          of the two actually exist for that card).
#   2. Base Set         - numbered cards only. Every one of {N, H, RH} that
#                          exists for that card checked.
#   3. Special Set Base - numbered cards only. Every one of {N, H, RH} PLUS
#                          every Poke Ball variant that exists checked.
#   4. Master Set       - same variant rule as Special Set Base, extended to
#                          EVERY card in the set, including "extra"/secret
#                          cards numbered above card_set.total_cards.
#   5. Grand Master     - Master Set + Promos. NOT IMPLEMENTED YET.
#
# ── Simple sets ─────────────────────────────────────────────────────────────
# Sets where no card has more than one checkable variant (most Trainer
# Gallery / Galarian Gallery / McDonald's / Trick or Trade / other one-print
# special sets) collapse the whole ladder into a single "Complete Set" tier
# instead -- there's nothing to distinguish tiers 1-4 when there's only ever
# one variant per card. This is detected automatically from the actual
# product data, not hand-flagged per set, so it self-corrects if a set turns
# out to have more variant depth than expected.
#
# ── Excluded ────────────────────────────────────────────────────────────────
# Sets under the "Prize Pack Series" era are excluded entirely -- it's not a
# fixed-size set (the same cards get reprinted across overlapping numbered
# series), so there's no stable 100% to hit.
#
# Non-standard variant codes (TR, SE, PBP, MBP, CC -- Team Rocket, Secret,
# PB/MB "pattern" promo stamps, Code Card) never gate any tier. If a product
# carries one of these, it's a bonus pull outside the ladder, not a
# requirement.
#
# NOTE on TT vs TK set codes (confirmed with Michael, 2026-07-30): these
# look similar but are UNRELATED product lines --
#   TT22 / TT23 / TT24 = Trick or Trade Halloween BOOster Bundles (era
#     "Trick or Trade", era_code TOT). Every card in these sets uses
#     variant_override "TT" -- that's the real, single-print variant for
#     the whole product line, not a bonus/promo tag, so "TT" IS in
#     FULL_VARIANTS below and DOES gate the (single, since these are
#     simple sets) tier.
#   TK22 / TK23 / TK24 = Trainer Kits, a completely different product line
#     that happens to share the year-suffixed naming pattern. Do not
#     confuse the two -- TK sets are NOT Trick or Trade and are out of
#     scope for the "TorT" work. (Their CardSet.name in the DB currently
#     still says "Trick or Trade 20XX", which is a mislabel left over from
#     an earlier import script -- worth a follow-up cleanup, but harmless
#     for this module since we key everything off card_set.code, not name.)

from collections import defaultdict

from .models import PokemonProduct, CardSet, ChecklistEntry

EXCLUDED_ERA_NAMES = {"Prize Pack Series"}

BROKE_BASE_VARIANTS = frozenset({"N", "H"})
BASE_SET_VARIANTS = frozenset({"N", "H", "RH"})
BALL_VARIANTS = frozenset({"PB", "MB", "LB", "FB", "QB", "UB", "DB"})
# "TT" is the single real print variant for every card in the Trick or
# Trade sets (TT22/TT23/TT24) -- see the note above. It's not a ball
# variant, but it needs to count toward completion the same way N does for
# a normal set, so it belongs in FULL_VARIANTS.
OTHER_TRACKED_VARIANTS = frozenset({"TT"})
FULL_VARIANTS = BASE_SET_VARIANTS | BALL_VARIANTS | OTHER_TRACKED_VARIANTS  # Special Set Base + Master Set scope

TIER_ORDER = ["broke_base", "base_set", "special_set_base", "master_set"]
TIER_LABELS = {
    "broke_base": "Broke Base",
    "base_set": "Base Set",
    "special_set_base": "Special Set Base",
    "master_set": "Master Set",
    "complete_set": "Complete Set",
}


def is_set_eligible(card_set: CardSet) -> bool:
    """False for Prize Pack Series sets -- everything else (including Trick
    or Trade, McDonald's, Trainer Gallery/Galarian Gallery satellites) is in."""
    era_name = card_set.era.name if card_set.era else ""
    return era_name not in EXCLUDED_ERA_NAMES


def _fallback_display_num(card_number: int, total_cards: int) -> str:
    """Used only when PokemonProduct.number is blank (the normal case for
    ordinary numbered sets). Must match the frontend exactly -- see
    checklists/page.tsx, where the key is built as `card.num + '_' + v.vc`
    and card.num is "{card_number zero-padded to 3 digits}/{total_cards}"."""
    return f"{str(card_number).zfill(3)}/{total_cards}"


def get_set_card_map(card_set: CardSet) -> dict:
    """
    {display_num: {"card_number": int, "variants": {variant_codes...}}} for
    every active product in this set, restricted to variant codes that
    count toward a tier at all.

    display_num is PokemonProduct.number when populated (e.g. "056/172"),
    NOT a value we reconstruct from card_number + card_set.total_cards.
    This matters: plain card_number is not a reliable per-card identifier
    for reprint-heavy sets like Trick or Trade. Confirmed in TT22 --
    Mewtwo and Haunter are BOTH card_number 56 (each keeps the number from
    the different original set it was reprinted from), and are only
    distinguished by their own `number` field: "056/172" vs "056/198".

    Even `number` itself can genuinely clash -- confirmed with Michael,
    2026-07-30: TT22's Nickit and Ariados are BOTH physically printed
    "103/189" (two different original sets that happened to share a card
    count and position). That's why PokemonProduct.id/SKU exists -- it's
    the one thing guaranteed unique per physical card -- so when a
    display_num is shared by more than one DISTINCT PHYSICAL CARD, we
    disambiguate with (the lowest) product id among that card's own rows
    (e.g. "103/189-404513"). Falls back to the zero-padded
    card_number/total_cards form when `number` is blank, which is the
    normal case for ordinary sets (ASC, SIT, etc.) and matches what the
    frontend already generates for those.

    BUG FIXED 2026-07-30 (caught via Michael reporting completed CRZ
    Master Set / ASC Base Set not registering): the disambiguation above
    used to count raw PRODUCT ROWS sharing a display_num, not distinct
    cards. A single physical card with N + H + RH variants is 2-3 rows
    that legitimately share the exact same `number` string -- that's the
    ORDINARY case for every non-simple set, not a collision. The old code
    treated that as a clash and split each variant row onto its own
    "-{id}" key, which the frontend (which only ever sends plain
    "num_variant") could never reproduce -- so effectively every
    multi-variant card in every "full" tier set silently failed to
    register as owned, even when fully checked. Fixed by grouping rows
    into (display_num, name) card-groups first: a display_num only gets
    disambiguated when it's shared by more than one DISTINCT NAME (a
    genuine different-card collision like Nickit vs Ariados). Rows that
    share both display_num and name -- the same card's own print variants
    -- always merge into one entry, using the lowest product id in that
    name-group as a stable suffix so every variant row of the same card
    still resolves to the identical key.
    """
    products = (
        PokemonProduct.objects
        .filter(card_set=card_set, is_active=True)
        .exclude(card_number__isnull=True)
        .values("id", "card_number", "variant_override", "number", "name")
    )
    total_cards = card_set.total_cards or 0

    # First pass: compute the raw display_num for every row and group rows
    # by (display_num, name) -- same display_num + same name is one
    # physical card's print variants (must merge); same display_num +
    # different name is a genuine collision (must stay apart).
    groups = defaultdict(list)  # (display_num, name) -> [(product, variant), ...]
    names_by_display_num = defaultdict(set)
    for p in products:
        variant = p["variant_override"] or "N"
        if variant not in FULL_VARIANTS:
            continue
        display_num = (p["number"] or "").strip() or _fallback_display_num(p["card_number"], total_cards)
        groups[(display_num, p["name"])].append((p, variant))
        names_by_display_num[display_num].add(p["name"])

    card_map = {}
    for (display_num, _name), rows in groups.items():
        if len(names_by_display_num[display_num]) == 1:
            key = display_num
        else:
            # Genuine collision -- stable suffix so every variant row of
            # THIS card (not the other one sharing display_num) lands on
            # the same key regardless of processing order.
            rep_id = min(p["id"] for p, _ in rows)
            key = f"{display_num}-{rep_id}"
        entry = card_map.setdefault(key, {"card_number": rows[0][0]["card_number"], "variants": set()})
        for p, variant in rows:
            entry["variants"].add(variant)
    return card_map


def is_simple_set(card_map: dict) -> bool:
    """True if no card in the set has more than one checkable variant."""
    if not card_map:
        return True
    return all(len(entry["variants"]) <= 1 for entry in card_map.values())


def _tier_progress(scope: dict, variant_filter: frozenset, checked_keys: set) -> dict:
    """Shared scoring for one tier: only ever requires variants that
    actually exist for a card (never a phantom variant the set doesn't
    print), and 'any' vs 'all' semantics are handled per-tier by the caller
    passing the right variant_filter/scope combination."""
    required = 0
    owned = 0
    for display_num, entry in scope.items():
        eligible = entry["variants"] & variant_filter
        if not eligible:
            continue
        required += len(eligible)
        for v in eligible:
            if f"{display_num}_{v}" in checked_keys:
                owned += 1
    pct = round(owned / required * 100) if required else 0
    return {"owned": owned, "required": required, "pct": pct, "complete": required > 0 and owned == required}


def _broke_base_progress(numbered: dict, checked_keys: set) -> dict:
    """Different shape from the other tiers: one requirement per card
    (satisfied by ANY of its N/H prints), not one per variant."""
    required = 0
    owned = 0
    for display_num, entry in numbered.items():
        eligible = entry["variants"] & BROKE_BASE_VARIANTS
        if not eligible:
            continue
        required += 1
        if any(f"{display_num}_{v}" in checked_keys for v in eligible):
            owned += 1
    pct = round(owned / required * 100) if required else 0
    return {"owned": owned, "required": required, "pct": pct, "complete": required > 0 and owned == required}


def compute_set_completion(card_set: CardSet, checked_keys: set) -> dict:
    """
    checked_keys: the card_key strings this user has checked for THIS
    card_set (i.e. already filtered by card_set=card_set.code).

    Returns {"mode": "simple", "tiers": {...}} or {"mode": "full", "tiers": {...}}.
    Each tier is {"owned", "required", "pct", "complete"}.
    """
    card_map = get_set_card_map(card_set)
    total_cards = card_set.total_cards or 0
    if total_cards:
        numbered = {k: v for k, v in card_map.items() if v["card_number"] <= total_cards}
    else:
        numbered = card_map  # total_cards not populated yet -- treat everything as numbered

    if is_simple_set(card_map):
        tier = _tier_progress(card_map, FULL_VARIANTS, checked_keys)
        return {"mode": "simple", "tiers": {"complete_set": tier}}

    tiers = {
        "broke_base": _broke_base_progress(numbered, checked_keys),
        "base_set": _tier_progress(numbered, BASE_SET_VARIANTS, checked_keys),
        "special_set_base": _tier_progress(numbered, FULL_VARIANTS, checked_keys),
        "master_set": _tier_progress(card_map, FULL_VARIANTS, checked_keys),
    }
    return {"mode": "full", "tiers": tiers}


def compute_user_set_completion(user, card_set: CardSet) -> dict:
    checked_keys = set(
        ChecklistEntry.objects
        .filter(user=user, card_set=card_set.code)
        .values_list("card_key", flat=True)
    )
    return compute_set_completion(card_set, checked_keys)
