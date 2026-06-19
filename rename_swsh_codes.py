"""
rename_swsh_codes.py

ONE-OFF migration script. Run this BEFORE re-running sync_tcgcsv.py for any
of the renamed SWSH-era sets, or get_or_create() will create brand-new
duplicate CardSet rows under the new code and orphan all existing products
under the old one.

Run via:
    python manage.py shell < rename_swsh_codes.py

Or paste into `python manage.py shell` interactively.

CRITICAL: DATABASE_URL must be uncommented in .env before running this,
so it hits Railway, not local SQLite.

This script is SAFE to re-run (idempotent) — if a CardSet with the old
code no longer exists (already renamed), it's skipped with a message
rather than erroring.
"""

from django.db import transaction
from products.models import CardSet, PokemonProduct

# (old_code, new_code) -- order matters for the BST chain:
# the set currently misusing "BST" (Brilliant Stars Trainer Gallery) must
# move OUT to BRSTG before SWSH05 moves IN to claim "BST", otherwise the
# old.code='BST' row would collide with the new one being created.
RENAMES = [
    ("BST", "BRSTG"),     # Brilliant Stars Trainer Gallery moves out first
    ("SWSH01", "SSH"),
    ("SWSH02", "RCL"),
    ("SWSH03", "DAA"),
    ("SWSH04", "VIV"),
    ("SWSH05", "BST"),    # Battle Styles claims BST last, now it's free
    ("SWSH06", "CRE"),
    ("SWSH07", "EVS"),
    ("SWSH08", "FST"),
    ("SWSH09", "BRS"),
    ("SWSH10", "ASR"),
    ("SWSH11", "LOR"),
    ("SWSH12", "SIT"),
]

print("=" * 70)
print("SWSH CardSet code rename — starting")
print("=" * 70)

with transaction.atomic():
    for old_code, new_code in RENAMES:
        try:
            card_set = CardSet.objects.get(code=old_code)
        except CardSet.DoesNotExist:
            print(f"  SKIP  {old_code:10s} -> {new_code:10s}  (no CardSet with code={old_code}, already renamed?)")
            continue

        # Guard: if a CardSet with the new_code already exists AND it isn't
        # this same row, something is wrong (real collision) — stop here
        # rather than silently merging two different sets together.
        existing_target = CardSet.objects.filter(code=new_code).exclude(pk=card_set.pk).first()
        if existing_target:
            print(f"  !!!!  ABORTING. CardSet code={new_code} already exists "
                  f"(id={existing_target.pk}, name={existing_target.name}) and is NOT "
                  f"the same row as {old_code} (id={card_set.pk}). Investigate before re-running.")
            raise SystemExit(1)

        product_count = PokemonProduct.objects.filter(card_set=card_set).count()

        old_name = card_set.name
        card_set.code = new_code
        card_set.save(update_fields=["code"])

        print(f"  OK    {old_code:10s} -> {new_code:10s}  "
              f"(name='{old_name}', {product_count} products carried over, id={card_set.pk})")

print("=" * 70)
print("CardSet rename complete. Now updating PokemonProduct.pb_id strings...")
print("=" * 70)

# pb_id format is f"{set_code}-{card_number}-{variant}" so every product
# under a renamed set needs its pb_id string rewritten to match.
new_codes = [new for _, new in RENAMES]

with transaction.atomic():
    for new_code in new_codes:
        try:
            card_set = CardSet.objects.get(code=new_code)
        except CardSet.DoesNotExist:
            print(f"  SKIP  pb_id update for {new_code} (CardSet not found, see above)")
            continue

        products = PokemonProduct.objects.filter(card_set=card_set)
        updated = 0
        for prod in products:
            # pb_id is f"{set_code}-{card_number}-{variant}" — rebuild it
            # from the fields directly rather than string-replacing the old
            # code prefix, since old code length varies (SWSH01 vs BST).
            expected_pb_id = f"{new_code}-{prod.card_number}-{prod.variant_override}"
            if prod.pb_id != expected_pb_id:
                prod.pb_id = expected_pb_id
                prod.save(update_fields=["pb_id"])
                updated += 1

        print(f"  OK    {new_code:10s}  {updated}/{products.count()} pb_id strings rewritten")

print("=" * 70)
print("DONE. Next step: run the REAL (non-dry-run) sync per renamed/new set")
print("to backfill any missing variants, e.g.:")
print("  python manage.py sync_tcgcsv --set-code SSH")
print("  python manage.py sync_tcgcsv --set-code LOR")
print("  ...etc for all 13 renamed codes, plus DX / CCP / EXBS (new sets,")
print("  no rename needed, just run sync directly).")
print("=" * 70)
