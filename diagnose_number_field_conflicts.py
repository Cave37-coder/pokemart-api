# PokeBulk SA -- finds rows where BOTH card_number and the raw `number`
# text field are populated at once, which should never happen under
# sync_tcgcsv.py's current convention (number=(number_raw or "") IF
# card_number is None ELSE "" -- see that file's own comment). A row with
# both set means whatever wrote it took a different path, and its `number`
# string wins over the normal zero-padded card_number/total_cards fallback
# when generate_checklist_data.py / completion.py compute a card's
# display_num -- so if that stored number's own embedded total doesn't
# match the set's real total_cards, the row gets a display_num that will
# never match its sibling variants' (e.g. Zarude in CRZ: one row correctly
# falls back to "016/159", another has a literal, wrong "016/293" baked in
# and never merges with it).
#
# READ-ONLY. Makes no DB changes.
#
# Usage:
#   python diagnose_number_field_conflicts.py --set=CRZ
#   python diagnose_number_field_conflicts.py --era=SWSH
#   python diagnose_number_field_conflicts.py --all

import argparse
import django
import os
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import CardSet, PokemonProduct

NUM_RE = re.compile(r"^(\d+)/(\d+)$")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", type=str, default=None)
    parser.add_argument("--era", type=str, default=None)
    parser.add_argument("--all", action="store_true")
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

    print(f"Scanning {len(card_sets)} set(s) for rows with BOTH card_number and number populated...\n")

    total_conflicts = 0
    total_mismatched_total = 0
    for card_set in card_sets:
        rows = list(
            PokemonProduct.objects
            .filter(card_set=card_set, is_active=True, card_number__isnull=False)
            .exclude(number="")
            .values("id", "name", "card_number", "number", "variant_override", "rarity", "price", "tcgcsv_product_id")
        )
        if not rows:
            continue
        total_conflicts += len(rows)
        print(f"=== {card_set.code} ({card_set.name}, total_cards={card_set.total_cards}) -- {len(rows)} row(s) ===")
        for r in rows:
            m = NUM_RE.match(r["number"])
            flag = ""
            if m and int(m.group(2)) != card_set.total_cards:
                flag = f"  <-- embedded total {m.group(2)} != set's real total_cards {card_set.total_cards}"
                total_mismatched_total += 1
            print(
                f"  id={r['id']} {r['name']!r} card_number={r['card_number']} number={r['number']!r} "
                f"variant={r['variant_override']!r} rarity={r['rarity']!r} price={r['price']} "
                f"tcgcsv_id={r['tcgcsv_product_id']}{flag}"
            )
        print()

    if total_conflicts == 0:
        print("None found -- every row follows the expected convention.")
    else:
        print(f"TOTAL: {total_conflicts} row(s) with both fields populated, {total_mismatched_total} of those with a")
        print("clearly wrong embedded total (mismatches CardSet.total_cards) -- those are the ones most likely to be")
        print("silently splitting a card into a duplicate tile like Zarude. Nothing written -- paste this back before")
        print("we decide how to fix them (likely: blank out `number` on the mismatched rows so they fall back to the")
        print("normal formula, same as their sibling variants already do).")


if __name__ == "__main__":
    main()
