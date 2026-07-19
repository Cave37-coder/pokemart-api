"""
fix_meg_era_assignment.py

Known bug (documented): ASC, PFL, POR, CRI CardSet rows are incorrectly
tagged era='SV' instead of era='MEG'. Confirmed against the bible CSV,
which authoritatively shows era='Mega Evolution' for all of these:
    MEG, PFL, ASC, POR, CRI, PBL

This checks all six (not just the four originally flagged) in case any
others have the same mistake, and fixes whichever are actually wrong.

Usage:
    python manage.py shell -c "exec(open('fix_meg_era_assignment.py').read())"

DRY RUN by default -- shows what would change, changes nothing.
Set APPLY = True to actually save.
"""

from products.models import CardSet

APPLY = False  # flip to True once the dry-run output looks right

MEG_SET_CODES = ['MEG', 'PFL', 'ASC', 'POR', 'CRI', 'PBL']
CORRECT_ERA = 'MEG'

print(f"Mode: {'APPLY (writing changes)' if APPLY else 'DRY RUN (no changes will be saved)'}")
print()

mismatches = []
for code in MEG_SET_CODES:
    cs = CardSet.objects.filter(code=code).first()
    if not cs:
        print(f"  {code}: NOT FOUND in DB -- skipping")
        continue
    current_era = getattr(cs, 'era', None)
    if current_era != CORRECT_ERA:
        mismatches.append(cs)
        print(f"  {code}: era={current_era!r} -> should be {CORRECT_ERA!r} (MISMATCH)")
    else:
        print(f"  {code}: era={current_era!r} -- already correct")

print()
print(f"Found {len(mismatches)} CardSet(s) needing correction.")

if APPLY and mismatches:
    for cs in mismatches:
        old = cs.era
        cs.era = CORRECT_ERA
        cs.save()
        print(f"  Updated {cs.code}: era {old!r} -> {CORRECT_ERA!r}")
    print(f"\nDone. Updated {len(mismatches)} CardSet row(s).")
elif mismatches:
    print("\nDry run only -- no changes saved. Set APPLY = True and re-run to apply.")
else:
    print("\nNothing to fix -- all six sets already correctly tagged.")
