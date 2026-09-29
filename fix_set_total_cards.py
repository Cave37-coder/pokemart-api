# PokeBulk SA -- STEP 1 of the CardSet.total_cards fix.
#
# Michael, 2026-09-29: diagnose_number_field_conflicts.py --era=SWSH showed
# 3603 rows across 23 sets where the raw `number` field's own embedded
# "/XXX" total disagrees with CardSet.total_cards -- and for every regular
# main set, ALL (or nearly all) of that set's own conflicting rows agree
# with EACH OTHER on one single total, just not with CardSet.total_cards.
# That's not noise -- it's every card in the set voting the same way. e.g.:
#
#   CRZ: 252/252 rows say "159"   -- total_cards is currently 293
#   CHP: 73/73 rows say "73"      -- total_cards is currently 147
#   PGO: 123/123 rows say "78"    -- total_cards is currently 165
#   SIT: 215/215 rows say "195"   -- total_cards is currently 386
#   SSH: 216/216 rows say "202"   -- total_cards is currently 425
#
# These "voted" numbers are also each set's real, official printed card
# count (Crown Zenith = 159 cards, Champion's Path = 73, Pokemon GO = 78,
# Silver Tempest = 195, Sword & Shield base = 202, etc.) -- so the
# conclusion is CardSet.total_cards itself has been wrong for a long list
# of SWSH-era sets, almost certainly since some past import, and every
# card in those sets has been quietly agreeing on the correct number the
# whole time in their own `number` field.
#
# This script finds that per-set consensus automatically (no hardcoded
# list of "right" answers) by looking at every active row in a set that has
# a non-blank `number` field -- not just the ones flagged by the earlier
# conflict diagnostic -- and taking whichever embedded total the large
# majority of them agree on. Three outcomes per set:
#
#   MATCH     consensus == current total_cards -- nothing to do.
#   MISMATCH  a dominant majority (>=90% of number-bearing rows) agree on
#             one total that differs from total_cards -- this is the bug;
#             --apply will correct total_cards to the consensus value.
#   MIXED     no dominant majority (e.g. CCC, a Classic Collection of
#             reprints where each card legitimately keeps ITS OWN original
#             set's total) -- never auto-changed, printed for visibility
#             only. Same for the *TG/*SV subsets, which will just show
#             MATCH since their own numbering is already self-consistent.
#
# Dry-run by default. Nothing is written unless you pass --apply.
#
# Usage:
#   python fix_set_total_cards.py --era=SWSH
#   python fix_set_total_cards.py --era=SWSH --apply
#   python fix_set_total_cards.py --set=CRZ --apply

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
    """Returns (consensus_total_or_None, counter, sample_size)."""
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
        return None, totals, 0
    top_total, top_count = totals.most_common(1)[0]
    if top_count / n >= MAJORITY_THRESHOLD:
        return top_total, totals, n
    return None, totals, n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", type=str, default=None)
    parser.add_argument("--era", type=str, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write corrected total_cards. Default is dry-run.")
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
    print(f"{mode} -- checking {len(card_sets)} set(s) for a total_cards consensus mismatch...\n")

    mismatches = []
    mixed = []
    for card_set in card_sets:
        consensus, totals, n = consensus_for_set(card_set)
        if n == 0:
            continue  # no rows with an explicit number field at all -- nothing to compare
        if consensus is None:
            top = totals.most_common(3)
            mixed.append((card_set, top, n))
            continue
        if consensus == card_set.total_cards:
            continue  # MATCH -- silent, nothing to report
        mismatches.append((card_set, consensus, totals[consensus], n))

    if mismatches:
        print("=== MISMATCH -- total_cards disagrees with what this set's own cards say ===")
        for card_set, consensus, votes, n in mismatches:
            print(
                f"  {card_set.code:8s} ({card_set.name}): total_cards={card_set.total_cards} "
                f"-> should be {consensus}  ({votes}/{n} rows agree, {votes/n:.0%})"
            )
        print()

    if mixed:
        print("=== MIXED -- no dominant total, left untouched (likely a reprint/tribute set) ===")
        for card_set, top, n in mixed:
            top_str = ", ".join(f"{t}x{c}" for t, c in top)
            print(f"  {card_set.code:8s} ({card_set.name}): total_cards={card_set.total_cards}, sample={n}, top totals: {top_str}")
        print()

    if not mismatches and not mixed:
        print("No mismatches found -- every set's total_cards already agrees with its own cards.")
        return

    if not mismatches:
        return

    if args.apply:
        print("Applying corrections...")
        for card_set, consensus, votes, n in mismatches:
            old = card_set.total_cards
            card_set.total_cards = consensus
            card_set.save(update_fields=["total_cards"])
            print(f"  {card_set.code}: total_cards {old} -> {consensus}")
        print(f"\nDone. Corrected {len(mismatches)} set(s).")
        print("Next: run fix_mismatched_numbers.py (dry-run) to find the individual rows still")
        print("carrying a stale `number` value from before these sets' totals were fixed.")
    else:
        print(f"{len(mismatches)} set(s) would be corrected. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
