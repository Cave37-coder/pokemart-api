# PokeBulk SA -- STEP 2 of the CardSet.total_cards fix, run AFTER
# fix_set_total_cards.py --apply.
#
# Once a set's total_cards is corrected, MOST rows that had both
# card_number and a non-blank `number` populated turn out to already agree
# with the (now-correct) total_cards -- e.g. CRZ's 252 conflicting rows all
# said ".../159", and total_cards is now 159, so those rows were already
# fine and just violated the "don't populate both fields" convention
# harmlessly. This script does NOT touch those.
#
# What it DOES fix is the smaller, actually-broken minority: rows whose
# `number` field disagrees with their OWN set's consensus even after the
# total_cards correction -- this is precisely the Zarude-in-CRZ bug. That
# row (RH variant, pid=446939) has card_number=NULL and number='016/293',
# while every other CRZ row agrees the set's total is 159 -- so Zarude's RH
# variant never computes the same display_num as its H sibling and shows up
# as a second, orphaned tile.
#
# For each such outlier row, found per-set against that set's OWN
# consensus (not a hardcoded number), this script:
#   - if card_number is already set: blanks `number` (the normal
#     card_number/total_cards fallback formula now produces the correct,
#     consensus-matching value on its own).
#   - if card_number is NULL: pulls the numerator straight out of the
#     existing `number` string (e.g. "016" from "016/293"), writes it into
#     card_number, and blanks `number` -- putting the row into the exact
#     same normal shape as its sibling variants, so it merges with them.
#
# Sets with no dominant consensus (MIXED, e.g. CCC where each reprinted
# card legitimately keeps its original set's own total) are always
# skipped entirely -- there is no single "correct" answer to compare
# against for those, so nothing in them is ever touched by this script.
#
# Dry-run by default. Nothing is written unless you pass --apply.
#
# Usage:
#   python fix_mismatched_numbers.py --era=SWSH
#   python fix_mismatched_numbers.py --era=SWSH --apply
#   python fix_mismatched_numbers.py --set=CRZ --apply

import argparse
import django
import os
import re
from collections import Counter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import CardSet, PokemonProduct

NUM_RE = re.compile(r"^(\d+)/(\d+)$")
MAJORITY_THRESHOLD = 0.90


def consensus_for_set(card_set):
    rows = (
        PokemonProduct.objects
        .filter(card_set=card_set, is_active=True)
        .exclude(number="")
        .values_list("number", flat=True)
    )
    totals = Counter()
    n = 0
    for raw in rows:
        m = NUM_RE.match((raw or "").strip())
        if not m:
            continue
        totals[int(m.group(2))] += 1
        n += 1
    if n == 0:
        return None, n
    top_total, top_count = totals.most_common(1)[0]
    if top_count / n >= MAJORITY_THRESHOLD:
        return top_total, n
    return None, n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", type=str, default=None)
    parser.add_argument("--era", type=str, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write fixes. Default is dry-run.")
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
        print("No matching CardSet(s) found.")
        return

    mode = "APPLYING CHANGES" if args.apply else "DRY RUN (pass --apply to write)"
    print(f"{mode} -- checking {len(card_sets)} set(s) for rows that still disagree with their set's own consensus...\n")

    total_fixed = 0
    total_skipped_mixed = 0
    for card_set in card_sets:
        consensus, n = consensus_for_set(card_set)
        if n == 0:
            continue
        if consensus is None:
            total_skipped_mixed += 1
            continue  # MIXED set (e.g. CCC) -- never touched

        rows = list(
            PokemonProduct.objects
            .filter(card_set=card_set, is_active=True)
            .exclude(number="")
            .values("id", "name", "card_number", "number", "variant_override", "pb_id")
        )
        bad_rows = []
        for r in rows:
            m = NUM_RE.match(r["number"].strip())
            if not m or int(m.group(2)) == consensus:
                continue
            bad_rows.append(r)

        if not bad_rows:
            continue

        print(f"=== {card_set.code} ({card_set.name}) -- consensus={consensus}, {len(bad_rows)} outlier row(s) ===")
        for r in bad_rows:
            m = NUM_RE.match(r["number"].strip())
            numerator = int(m.group(1))
            new_display = f"{str(r['card_number'] if r['card_number'] is not None else numerator).zfill(3)}/{consensus}"
            if r["card_number"] is not None:
                action = f"blank number (was {r['number']!r}) -- falls back to {str(r['card_number']).zfill(3)}/{consensus}"
            else:
                action = f"set card_number={numerator}, blank number (was {r['number']!r}) -- becomes {new_display}"
            print(f"  id={r['id']} {r['name']!r} variant={r['variant_override']!r} pb_id={r['pb_id']!r}: {action}")
            total_fixed += 1

            if args.apply:
                obj = PokemonProduct.objects.get(id=r["id"])
                if obj.card_number is None:
                    obj.card_number = numerator
                obj.number = ""
                obj.save(update_fields=["card_number", "number"])
        print()

    if total_skipped_mixed:
        print(f"(Skipped {total_skipped_mixed} MIXED set(s) with no single consensus -- e.g. reprint collections. Untouched.)\n")

    if total_fixed == 0:
        print("No outlier rows found -- every row already agrees with its set's consensus.")
    elif args.apply:
        print(f"Done. Fixed {total_fixed} row(s). Next: python manage.py generate_checklist_data, then redeploy.")
    else:
        print(f"{total_fixed} row(s) would be fixed. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
