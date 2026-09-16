# PokeBulk SA - Create 30th Celebration CardSets
# v1.0
#
# Creates two CardSet rows so sync_bible_to_db.py has something to attach
# products to:
#   30C  - the main 30th Celebration set (TCGCSV group_id 24722)
#   30CC - the 30th Celebration: Classic Collection subset (TCGCSV group_id
#          24837), following the exact same pattern as CLB/CCC (Celebrations
#          / Celebrations: Classic Collection, 2021) -- a parent set plus a
#          separately-grouped reprint subset, same era on both.
#
# Era: "MEG" (Mega Evolution) -- the current era, same one Pitch Black (PBL)
# uses, and the same "share the current era" pattern CLB/CCC used with
# Sword & Shield back in 2021.
#
# total_cards is deliberately left at 0 for both -- run fix_total_cards.py
# after the real sync to recalculate from actual synced product count,
# same convention as create_cardset_pbl.py. This is doubly true here since
# only 19 of the ~188 real cards in 30C have confirmed TCGCSV product_ids
# as of this writing (see 30TH_CELEBRATION_NEXT_STEPS.md) -- do not guess
# the number now.
#
# symbol_url is left blank -- add the real TCG set symbol once you have it.
#
# Run from C:\Users\texca\pokemart-api with DATABASE_URL uncommented:
#   python manage.py shell -c "exec(open('create_cardset_30th_celebration.py').read())"
#
# Dry-run by default. Set CARDSET_APPLY=1 to actually create the rows.

import os
from datetime import date
from products.models import CardSet, Era

APPLY = os.environ.get("CARDSET_APPLY") == "1"

ERA_CODE = "MEG"

SETS_TO_CREATE = [
    {
        "code": "30C",
        "name": "30th Celebration",
        "release_date": date(2026, 9, 16),
    },
    {
        "code": "30CC",
        "name": "30th Celebration: Classic Collection",
        "release_date": date(2026, 9, 16),
    },
]

print(f"Mode: {'APPLY (writing changes)' if APPLY else 'DRY RUN (no changes will be saved)'}")
print()

try:
    era = Era.objects.get(code=ERA_CODE)
except Era.DoesNotExist:
    print(f"ERROR: Era with code={ERA_CODE!r} does not exist. Expected it to already exist "
          f"(same era PBL/ME05 uses). Create the Era first, then rerun this script.")
    raise SystemExit(1)

print(f"Found Era: {era.code}")

for spec in SETS_TO_CREATE:
    existing = CardSet.objects.filter(code=spec["code"]).first()
    if existing:
        print(f"\nCardSet {spec['code']!r} already exists (id={existing.id}):")
        print(f"  name={existing.name!r} era={existing.era.code if existing.era else None!r} "
              f"release_date={existing.release_date} total_cards={existing.total_cards} "
              f"symbol_url={existing.symbol_url!r}")
        print("Nothing to do for this one -- delete it manually first if you need to recreate it.")
        continue

    print(f"\nCardSet {spec['code']!r} does not exist yet. Would create with:")
    print(f"  code         = {spec['code']!r}")
    print(f"  name         = {spec['name']!r}")
    print(f"  era          = {ERA_CODE!r}")
    print(f"  release_date = {spec['release_date']}")
    print(f"  total_cards  = 0  (recalculate later with fix_total_cards.py)")
    print(f"  symbol_url   = ''  (add once you have the real TCG set symbol)")

    if APPLY:
        new_set = CardSet.objects.create(
            code=spec["code"],
            name=spec["name"],
            era=era,
            release_date=spec["release_date"],
            total_cards=0,
            symbol_url="",
        )
        print(f"  Created CardSet id={new_set.id}")

if not APPLY:
    print("\nDry run only -- no changes saved. "
          "Re-run with CARDSET_APPLY=1 set in the environment to apply.")
