# PokeBulk SA -- STEP 3 of the number/total_cards fix, run after
# fix_set_total_cards.py --apply.
#
# Michael, 2026-09-30: after Step 1+2 shipped, CES/SM11/SM12 still show
# split tiles for a chunk of cards (Victreebel, Ariados in CES; Yanma,
# Celebi, Shroomish, Sewaddle in SM11/12), while FCO mostly merged fine
# (except its own Delphox). Screenshot shows the exact split-tile shape:
# one tile numbered "003" (zero-padded), its sibling numbered "3" (NOT
# padded) -- same card, same total (168 for CES), but two DIFFERENT
# strings, so they still don't merge.
#
# ROOT CAUSE: fix_mismatched_numbers.py (Step 2) only compared each row's
# embedded TOTAL (the denominator) against the set's consensus -- it never
# checked whether the NUMERATOR's zero-padding matched the fallback
# formula's convention (str(card_number).zfill(3)). Two rows can agree on
# the total (168) while one has a hand-baked `number` like "3/168" (no
# padding) and its sibling either has "003/168" baked in, or has `number`
# blank and falls back to fallback_display_num() -- which ALWAYS
# zero-pads to 3 digits. Different strings, same card, no merge. This is
# a different, narrower defect than Step 1/2 fixed (those were entirely
# correct for what they targeted -- the total mismatch) but doesn't cover
# padding-only mismatches.
#
# FIX: for every active row in a set with a known, non-MIXED total_cards
# (same MIXED detection as fix_set_total_cards.py -- reprints like CCC/
# TT22-24/SMP/SVP/PRIZEPACK are skipped, never touched), any row whose
# `number` is a plain "<digits>/<digits>" string gets normalized to
# EXACTLY what fallback_display_num(card_number, total_cards) would
# produce:
#   - card_number already set: blank `number` outright (trust
#     card_number, the authoritative field; this also cleans up the
#     "both fields populated" anti-pattern from Step 1/2's own diagnostic
#     regardless of whether the embedded total happened to already match).
#   - card_number is NULL: pull the numerator out of `number`, write it
#     into card_number, blank `number`.
# Either way every card in a set ends up computed by the exact same
# fallback formula, so siblings can never again disagree on padding.
# Non-numeric formats (Unown's "A/28".."Z/28", TG-prefixed, SV-prefixed)
# are left completely alone -- they were never part of this bug.
#
# Dry-run by default. Nothing is written unless you pass --apply.
#
# Usage:
#   python normalize_card_numbers.py --era=SWSH
#   python normalize_card_numbers.py --all --apply
#   python normalize_card_numbers.py --set=CES --apply

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


def fallback_display_num(card_number: int, total_cards: int) -> str:
    return f"{str(card_number).zfill(3)}/{total_cards}"


def is_mixed_set(card_set) -> bool:
    """Same consensus check as fix_set_total_cards.py: a set is MIXED
    (reprints/promos with legitimately different per-card totals) when no
    single total commands >=90% of the rows that have an explicit
    `number`. MIXED sets are never touched by this script."""
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
        return False
    _, top_count = totals.most_common(1)[0]
    return (top_count / n) < MAJORITY_THRESHOLD


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
    print(f"{mode} -- normalizing card numbers in {len(card_sets)} set(s) to the fallback formula's exact formatting...\n")

    total_fixed = 0
    total_skipped_mixed = 0
    total_skipped_no_total = 0

    for card_set in card_sets:
        total = card_set.total_cards or 0
        if total == 0:
            total_skipped_no_total += 1
            continue
        if is_mixed_set(card_set):
            total_skipped_mixed += 1
            continue

        rows = list(
            PokemonProduct.objects
            .filter(card_set=card_set, is_active=True)
            .values("id", "name", "card_number", "number", "variant_override", "pb_id")
        )

        bad_rows = []
        for r in rows:
            raw_number = (r["number"] or "").strip()
            if r["card_number"] is not None:
                # Both populated is already an anomaly per sync_tcgcsv.py's
                # convention -- trust card_number, blank number regardless
                # of whether its embedded total/padding happened to match.
                if raw_number != "":
                    canonical = fallback_display_num(r["card_number"], total)
                    bad_rows.append((r, None, canonical, raw_number))
                continue
            # card_number is NULL -- only consider plain digit/digit numbers
            m = NUM_RE.match(raw_number)
            if not m:
                continue  # letter-numbered / TG- / SV-prefixed -- leave alone
            numerator = int(m.group(1))
            canonical = fallback_display_num(numerator, total)
            if raw_number != canonical:
                bad_rows.append((r, numerator, canonical, raw_number))

        if not bad_rows:
            continue

        print(f"=== {card_set.code} ({card_set.name}) -- total_cards={total}, {len(bad_rows)} row(s) to normalize ===")
        for r, numerator, canonical, old_number in bad_rows:
            if numerator is None:
                action = f"blank number (was {old_number!r}) -- falls back to {fallback_display_num(r['card_number'], total)}"
            else:
                action = f"set card_number={numerator}, blank number (was {old_number!r}) -- becomes {canonical}"
            print(f"  id={r['id']} {r['name']!r} variant={r['variant_override']!r} pb_id={r['pb_id']!r}: {action}")
            total_fixed += 1

            if args.apply:
                obj = PokemonProduct.objects.get(id=r["id"])
                if obj.card_number is None and numerator is not None:
                    obj.card_number = numerator
                obj.number = ""
                obj.save(update_fields=["card_number", "number"])
        print()

    if total_skipped_mixed:
        print(f"(Skipped {total_skipped_mixed} MIXED set(s) with no single consensus total -- e.g. reprint collections. Untouched.)")
    if total_skipped_no_total:
        print(f"(Skipped {total_skipped_no_total} set(s) with total_cards=0 -- nothing to normalize against.)")

    if total_fixed == 0:
        print("\nNo rows needed normalizing -- every card number already matches the fallback formula exactly.")
    elif args.apply:
        print(f"\nDone. Normalized {total_fixed} row(s). Next: python manage.py generate_checklist_data, then redeploy.")
    else:
        print(f"\n{total_fixed} row(s) would be normalized. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
