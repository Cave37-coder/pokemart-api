# PokeBulk SA - Create PBL CardSet
# v1.0
#
# Creates the Pitch Black CardSet row so sync_bible_to_db.py has something
# to attach products to (it does card_sets.get(set_code) and just warns +
# skips if the CardSet doesn't exist yet).
#
# total_cards is deliberately left at 0 here -- run fix_total_cards.py after
# the real sync to recalculate it from actual synced product count, rather
# than guessing a number now (sources disagree: 84 / 118 / 120+ depending
# on whether secret rares/promos are counted).
#
# symbol_url is left blank -- add the real TCG set symbol once you have it,
# same as any other set (used by the Divider Tabs feature and Browse Cards).
#
# Assumes the 'MEG' Era already exists (it does -- it's the era shared by
# MEG, PFL, ASC, POR, CRI per your bulba era map). This script will error
# clearly rather than guess if it's missing.
#
# Run from C:\Users\texca\pokemart-api with DATABASE_URL uncommented:
#   python manage.py shell -c "exec(open('create_cardset_pbl.py').read())"
#
# Dry-run by default. Set APPLY = True (or set env var CARDSET_APPLY=1) to
# actually create the row.

import os
from datetime import date
from products.models import CardSet, Era

APPLY = os.environ.get("CARDSET_APPLY") == "1"

SET_CODE = "PBL"
SET_NAME = "ME05: Pitch Black"
ERA_CODE = "MEG"
RELEASE_DATE = date(2026, 7, 17)

print(f"Mode: {'APPLY (writing changes)' if APPLY else 'DRY RUN (no changes will be saved)'}")
print()

try:
    era = Era.objects.get(code=ERA_CODE)
except Era.DoesNotExist:
    print(f"ERROR: Era with code={ERA_CODE!r} does not exist. Expected it to already exist")
    print(f"(shared by MEG, PFL, ASC, POR, CRI). Create the Era first, then rerun this script.")
    raise SystemExit(1)

print(f"Found Era: {era.code}")

existing = CardSet.objects.filter(code=SET_CODE).first()
if existing:
    print(f"\nCardSet {SET_CODE!r} already exists (id={existing.id}):")
    print(f"  name={existing.name!r} era={existing.era.code if existing.era else None!r} "
          f"release_date={existing.release_date} total_cards={existing.total_cards} "
          f"symbol_url={existing.symbol_url!r}")
    print("\nNothing to do -- CardSet already present. Delete it manually first if you need to recreate it.")
else:
    print(f"\nCardSet {SET_CODE!r} does not exist yet. Would create with:")
    print(f"  code         = {SET_CODE!r}")
    print(f"  name         = {SET_NAME!r}")
    print(f"  era          = {ERA_CODE!r}")
    print(f"  release_date = {RELEASE_DATE}")
    print(f"  total_cards  = 0  (recalculate later with fix_total_cards.py)")
    print(f"  symbol_url   = ''  (add once you have the real TCG set symbol)")

    if APPLY:
        new_set = CardSet.objects.create(
            code=SET_CODE,
            name=SET_NAME,
            era=era,
            release_date=RELEASE_DATE,
            total_cards=0,
            symbol_url="",
        )
        print(f"\nCreated CardSet id={new_set.id}")
    else:
        print("\nDry run only -- no changes saved. "
              "Re-run with CARDSET_APPLY=1 set in the environment to apply.")
