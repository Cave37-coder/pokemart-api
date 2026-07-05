"""
fix_variant_sort_order.py

Corrects PokemonProduct.variant_sort values so ordering always follows:
N -> H -> RH -> PB -> MB -> LB -> FB -> QB -> UB -> DB -> TR -> SE -> PBP -> MBP -> CC -> TT

Root cause note: this only fixes EXISTING rows already in the Railway DB.
sync_tcgcsv.py still needs its own variant_sort assignment mapping corrected
separately (upload it and I'll patch it) or every future sync will keep
producing the same RH-before-H bug on new/re-synced rows.

Usage (per your PowerShell rule):
    python manage.py shell -c "exec(open('fix_variant_sort_order.py').read())"

Runs in DRY-RUN mode by default -- prints what WOULD change, changes nothing.
Set APPLY = True below (or set the env var VARIANT_SORT_APPLY=1) to actually write.
"""

import os
from products.models import PokemonProduct

APPLY = os.environ.get("VARIANT_SORT_APPLY") == "1"  # False = dry run

# Canonical order per the Iron Rule. Index = correct variant_sort value.
VARIANT_ORDER = [
    "N", "H", "RH",
    "PB", "MB", "LB", "FB", "QB", "UB", "DB",
    "TR", "SE", "PBP", "MBP", "CC", "TT",
]
VARIANT_SORT_MAP = {code: i for i, code in enumerate(VARIANT_ORDER)}
FALLBACK_SORT = 99  # unknown/blank variant codes sort last, unchanged behaviour

print(f"Mode: {'APPLY (writing changes)' if APPLY else 'DRY RUN (no changes will be saved)'}")

mismatches = []
total = PokemonProduct.objects.count()
checked = 0

for p in PokemonProduct.objects.only("id", "variant_override", "variant_sort", "card_number", "name").iterator(chunk_size=1000):
    checked += 1
    code = (p.variant_override or "N").strip()
    correct_sort = VARIANT_SORT_MAP.get(code, FALLBACK_SORT)
    if p.variant_sort != correct_sort:
        mismatches.append((p, correct_sort))

    if checked % 1000 == 0:
        print(f"  checked {checked}/{total}...")

print(f"Checked {checked} rows total.")
print(f"Found {len(mismatches)} rows with an incorrect variant_sort.")

if mismatches:
    print("\nSample of mismatches (first 20):")
    for p, correct_sort in mismatches[:20]:
        print(f"  [{p.card_number}] {p.name} — variant={p.variant_override or 'N'!r} "
              f"current_sort={p.variant_sort} -> correct_sort={correct_sort}")

if APPLY and mismatches:
    print("\nApplying fixes...")
    to_update = []
    for p, correct_sort in mismatches:
        p.variant_sort = correct_sort
        to_update.append(p)

    batch_size = 500
    for i in range(0, len(to_update), batch_size):
        batch = to_update[i:i + batch_size]
        PokemonProduct.objects.bulk_update(batch, ["variant_sort"])
        print(f"  saved {min(i + batch_size, len(to_update))}/{len(to_update)}...")

    print(f"\nDone. Updated {len(to_update)} rows.")
elif mismatches:
    print("\nDry run only -- no changes saved. "
          "Re-run with VARIANT_SORT_APPLY=1 set in the environment to apply.")
else:
    print("\nNothing to fix -- all variant_sort values already correct.")
