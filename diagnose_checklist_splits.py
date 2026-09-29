# PokeBulk SA -- diagnoses "same card showing as two separate checklist
# tiles instead of one tile with N/H/RH buttons".
#
# Michael, 2026-09-29, screenshot of /checklists?set=CRZ: Zarude (016)
# showed as TWO tiles -- one badged "H", one badged "RH" -- instead of one
# "016 - Zarude" tile with both buttons, like every other card on that page
# (Oddish, Gloom, etc. all correctly show one tile with N + RH buttons).
#
# ROOT CAUSE CANDIDATE: both generate_checklist_data.py's build_set_cards()
# and products/completion.py's _grouped_card_rows() (the shared grouping
# core used by progress/leaderboard/tier math too) only split one
# display_num into MULTIPLE tiles when the rows sharing it have 2+ DISTINCT
# `name` values (see _grouped_card_rows' docstring -- this is deliberate,
# for genuine reprint collisions like TT22's Mewtwo/Haunter both being
# card_number 56). A same-name, different-variant pair (H vs RH of the same
# Zarude) should never trigger that path -- variant_counts would be {H:1,
# RH:1}, not a collision at all. So if Zarude really did split, its two
# rows almost certainly have subtly DIFFERENT `name` strings that render
# identically on screen (trailing space, smart vs straight apostrophe,
# a hidden suffix, different casing) -- this script prints the raw name
# with repr() specifically to surface that.
#
# READ-ONLY. Makes no DB changes.
#
# Usage:
#   python diagnose_checklist_splits.py --set=CRZ
#   python diagnose_checklist_splits.py --era=SWSH        # every SWSH set
#   python diagnose_checklist_splits.py                    # every set, era=SWSH default excluded, use --all
#   python diagnose_checklist_splits.py --all

import argparse
import django
import os
from collections import Counter, defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import CardSet, PokemonProduct

FULL_VARIANTS = frozenset({
    "N", "H", "RH", "PB", "MB", "LB", "FB", "QB", "UB", "DB", "TT", "ESH",
})


def fallback_display_num(card_number, total_cards):
    return f"{str(card_number).zfill(3)}/{total_cards}"


def find_splits(card_set):
    """Returns a list of (display_num, {name: [(product_dict, variant), ...]})
    for every display_num in this set that would produce MORE THAN ONE
    checklist tile -- i.e. exactly the condition that splits one physical
    card into separate tiles."""
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

    splits = []
    for display_num, rows in rows_by_display_num.items():
        variant_counts = Counter(v for _, v in rows)
        is_genuine_collision = any(c > 1 for c in variant_counts.values())
        if not is_genuine_collision:
            continue  # single tile, exactly as intended -- not a split

        groups = defaultdict(list)
        for p, variant in rows:
            groups[p["name"]].append((p, variant))

        if len(groups) > 1:
            splits.append((display_num, groups))

    return splits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", type=str, default=None, help="Single CardSet code, e.g. CRZ")
    parser.add_argument("--era", type=str, default=None, help="Single Era code, e.g. SWSH")
    parser.add_argument("--all", action="store_true", help="Scan every set in the catalog")
    args = parser.parse_args()

    if args.set:
        card_sets = CardSet.objects.filter(code=args.set)
    elif args.era:
        card_sets = CardSet.objects.filter(era__code=args.era).order_by("code")
    elif args.all:
        card_sets = CardSet.objects.all().order_by("code")
    else:
        card_sets = CardSet.objects.filter(era__code="SWSH").order_by("code")

    card_sets = list(card_sets)
    if not card_sets:
        print("No matching CardSet(s) found -- check --set/--era spelling.")
        return

    print(f"Scanning {len(card_sets)} set(s) for split display_nums (same number, genuinely different names)...\n")

    total_splits = 0
    for card_set in card_sets:
        splits = find_splits(card_set)
        if not splits:
            continue
        total_splits += len(splits)
        print(f"=== {card_set.code} ({card_set.name}) -- {len(splits)} split display_num(s) ===")
        for display_num, groups in splits:
            print(f"  display_num={display_num!r} splits into {len(groups)} tile(s):")
            for name, rows in groups.items():
                print(f"    name={name!r}")
                for p, variant in rows:
                    print(
                        f"      id={p['id']} variant={variant!r} card_number={p['card_number']!r} "
                        f"number={p['number']!r} rarity={p['rarity']!r} price={p['price']} pb_id={p['pb_id']!r}"
                    )
        print()

    if total_splits == 0:
        print("No split display_nums found in the scanned set(s) -- every card merged into one tile.")
    else:
        print(f"TOTAL: {total_splits} split display_num(s) across {len(card_sets)} set(s) -- see detail above.")
        print("Nothing written -- this is read-only. Paste this output back so we can see exactly")
        print("what's different between the rows before deciding on a fix.")


if __name__ == "__main__":
    main()
