# PokeBulk SA - Delete Broken PBL Products
# v1.0
#
# Removes the 120 PBL PokemonProduct rows created by the buggy pb_id
# collision in sync_bible_to_db.py (fixed separately). These rows are safe
# to delete: PBL hasn't released yet, so there's zero real stock/orders on
# any of them -- all currently sit at the R1.50 placeholder price with
# stock=0.
#
# After running this, re-run the CORRECTED sync_bible_to_db.py to recreate
# all 194 rows properly (97 N, 23 H, 74 RH -- matching the dry-run plan).
#
# Run from C:\Users\texca\pokemart-api with DATABASE_URL uncommented:
#   python manage.py shell -c "exec(open('delete_broken_pbl_products.py').read())"
#
# Dry-run by default. Set APPLY = True (or set env var DELETE_PBL_APPLY=1)
# to actually delete.

import os
from products.models import PokemonProduct, CardSet

APPLY = os.environ.get("DELETE_PBL_APPLY") == "1"

print(f"Mode: {'APPLY (deleting rows)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

pbl = CardSet.objects.get(code='PBL')
products = PokemonProduct.objects.filter(card_set=pbl)
count = products.count()

print(f"Found {count} PokemonProduct rows for PBL.")

if count == 0:
    print("Nothing to delete.")
else:
    # Safety check: refuse to delete if any of these rows have real stock
    # or a non-placeholder price -- that would mean someone already started
    # working with this data and it's not safe to blindly wipe.
    suspicious = products.exclude(stock=0).count()
    non_placeholder_price = products.exclude(price=1.50).count()

    if suspicious > 0:
        print(f"\nWARNING: {suspicious} row(s) have non-zero stock. Refusing to auto-delete.")
        print("Review manually -- this script will not touch these rows.")
    elif non_placeholder_price > 0:
        print(f"\nWARNING: {non_placeholder_price} row(s) have a price other than the R1.50 placeholder.")
        print("Refusing to auto-delete -- review manually first.")
    else:
        print("Safety check passed: all rows are stock=0 with the R1.50 placeholder price.")
        print(f"\nWould delete {count} rows." if not APPLY else f"\nDeleting {count} rows...")

        if APPLY:
            deleted_count, _ = products.delete()
            print(f"Deleted {deleted_count} row(s).")
            print("\nNext step: re-run the corrected sync_bible_to_db.py to recreate all 194 rows properly.")
        else:
            print("\nDry run only -- no changes made. "
                  "Re-run with DELETE_PBL_APPLY=1 set in the environment to apply.")
