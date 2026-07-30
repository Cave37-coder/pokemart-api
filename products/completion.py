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
# Non-standard variant codes (TT, TR, SE, PBP, MBP, CC -- Trick or Trade
# reprint tags, Team Rocket, Secret, PB/MB "pattern" promo stamps, Code Card)
# never gate any tier. If a product carries one of these, it's a bonus pull
# outside the ladder, not a requirement.

from collections import defaultdict

from .models import PokemonProduct, CardSet, ChecklistEntry

EXCLUDED_ERA_NAMES = {"Prize Pack Series"}

BROKE_BASE_VARIANTS = frozenset({"N", "H"})
BASE_SET_VARIANTS = frozenset({"N", "H", "RH"})
BALL_VARIANTS = frozenset({"PB", "MB", "LB", "FB", "QB", "UB", "DB"})
FULL_VARIANTS = BASE_SET_VARIANTS | BALL_VARIANTS  # Special Set Base + Master Set scope

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


def _card_key(card_number: int, total_cards: int, variant: str) -> str:
    """Must match the frontend exactly -- see checklists/page.tsx, where the
    key is built as `card.num + '_' + v.vc` and card.num is
    "{card_number zero-padded to 3 digits}/{total_cards}"."""
    return f"{str(card_number).zfill(3)}/{total_cards}_{variant}"


def get_set_card_map(card_set: CardSet) -> dict:
    """{card_number: {variant_codes...}} for every active product in this
    set, restricted to variant codes that count toward a tier at all."""
    products = (
        PokemonProduct.objects
        .filter(card_set=card_set, is_active=True)
        .exclude(card_number__isnull=True)
        .values("card_number", "variant_override")
    )
    card_map = defaultdict(set)
    for p in products:
        variant = p["variant_override"] or "N"
        if variant not in FULL_VARIANTS:
            continue
        card_map[p["card_number"]].add(variant)
    return dict(card_map)


def is_simple_set(card_map: dict) -> bool:
    """True if no card in the set has more than one checkable variant."""
    if not card_map:
        return True
    return all(len(variants) <= 1 for variants in card_map.values())


def _tier_progress(scope: dict, variant_filter: frozenset, checked_keys: set, total_cards: int) -> dict:
    """Shared scoring for one tier: only ever requires variants that
    actually exist for a card (never a phantom variant the set doesn't
    print), and 'any' vs 'all' semantics are handled per-tier by the caller
    passing the right variant_filter/scope combination."""
    required = 0
    owned = 0
    for card_number, variants in scope.items():
        eligible = variants & variant_filter
        if not eligible:
            continue
        required += len(eligible)
        for v in eligible:
            if _card_key(card_number, total_cards, v) in checked_keys:
                owned += 1
    pct = round(owned / required * 100) if required else 0
    return {"owned": owned, "required": required, "pct": pct, "complete": required > 0 and owned == required}


def _broke_base_progress(numbered: dict, checked_keys: set, total_cards: int) -> dict:
    """Different shape from the other tiers: one requirement per card
    (satisfied by ANY of its N/H prints), not one per variant."""
    required = 0
    owned = 0
    for card_number, variants in numbered.items():
        eligible = variants & BROKE_BASE_VARIANTS
        if not eligible:
            continue
        required += 1
        if any(_card_key(card_number, total_cards, v) in checked_keys for v in eligible):
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
        numbered = {n: v for n, v in card_map.items() if n <= total_cards}
    else:
        numbered = card_map  # total_cards not populated yet -- treat everything as numbered

    if is_simple_set(card_map):
        tier = _tier_progress(card_map, FULL_VARIANTS, checked_keys, total_cards)
        return {"mode": "simple", "tiers": {"complete_set": tier}}

    tiers = {
        "broke_base": _broke_base_progress(numbered, checked_keys, total_cards),
        "base_set": _tier_progress(numbered, BASE_SET_VARIANTS, checked_keys, total_cards),
        "special_set_base": _tier_progress(numbered, FULL_VARIANTS, checked_keys, total_cards),
        "master_set": _tier_progress(card_map, FULL_VARIANTS, checked_keys, total_cards),
    }
    return {"mode": "full", "tiers": tiers}


def compute_user_set_completion(user, card_set: CardSet) -> dict:
    checked_keys = set(
        ChecklistEntry.objects
        .filter(user=user, card_set=card_set.code)
        .values_list("card_key", flat=True)
    )
    return compute_set_completion(card_set, checked_keys)
