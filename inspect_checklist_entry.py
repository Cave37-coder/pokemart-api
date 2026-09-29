# PokeBulk SA -- prints the exact, already-baked entries for a given
# set+number straight out of checklistData.ts, the file the checklist page
# actually renders from.
#
# Michael, 2026-09-30: after deploying today's fixes (variant_sort ordering
# + regenerated checklistData.ts), the N/RH button order looks fixed on
# /checklists?set=CRZ, but Zarude (016) is STILL showing as two separate
# tiles -- yet diagnose_checklist_splits.py --set=CRZ reported zero splits
# right after that same regeneration. Those two things can't both be true
# of the same data, so rather than guess again, this reads the ACTUAL
# shipped file directly (no re-deriving from the DB, no assumptions) so we
# can see exactly what's baked in for 016 and settle which of the two is
# stale/wrong.
#
# READ-ONLY. Makes no changes.
#
# Usage:
#   python inspect_checklist_entry.py --set CRZ --num 016
#   python inspect_checklist_entry.py --set CRZ --name Zarude
#   python inspect_checklist_entry.py --file "../pokemart-frontend/src/lib/checklistData.ts" --set CRZ --num 016

import argparse
import json
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default="../pokemart-frontend/src/lib/checklistData.ts")
    parser.add_argument("--set", type=str, required=True, help="CardSet code, e.g. CRZ")
    parser.add_argument("--num", type=str, default=None, help="Match cards whose num starts with this, e.g. 016")
    parser.add_argument("--name", type=str, default=None, help="Match cards whose name contains this, e.g. Zarude")
    args = parser.parse_args()

    if not args.num and not args.name:
        print("Pass --num and/or --name to filter which cards to show.")
        return

    with open(args.file, encoding="utf-8") as f:
        content = f.read()

    m = re.search(r"export const SETS: Record<string, SetData> = (\{.*?\});\n", content, re.DOTALL)
    if not m:
        print("Could not find the SETS blob in that file -- wrong path, or format changed.")
        return

    sets = json.loads(m.group(1))
    set_data = sets.get(args.set)
    if not set_data:
        print(f"No set {args.set!r} found in checklistData.ts. Sets present: {len(sets)} total.")
        return

    matches = [
        c for c in set_data["cards"]
        if (not args.num or c["num"].startswith(args.num))
        and (not args.name or args.name.lower() in c["name"].lower())
    ]

    print(f"Set {args.set} ({set_data['name']}) -- {len(set_data['cards'])} total card entries in the file.")
    print(f"Matched {len(matches)} entr(y/ies) for num~{args.num!r} name~{args.name!r}:\n")
    for c in matches:
        print(f"  num={c['num']!r} name={c['name']!r} rarity={c['rarity']!r}")
        for v in c["variants"]:
            print(f"      variant={v['vc']!r} pid={v['pid']} price=R{v['zar']}")
    if not matches:
        print("  (none -- check the --num/--name spelling, or the card may not exist in this set)")


if __name__ == "__main__":
    main()
