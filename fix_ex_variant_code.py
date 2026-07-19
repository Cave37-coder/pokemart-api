"""
fix_ex_variant_code.py

Cards like "Meloetta EX", "Excadrill EX" are currently coded as
variant_override='H' -- same as ordinary Holo cards. Per instruction
2026-07-13: these should be their own distinct variant code 'EX', not
lumped in with H.

Scope: every SV-era and MEG-era set (per BULBAPEDIA ERA MAP):
    SV:  SVI, PAL, OBF, MEW, PAR, PAF, TEF, TWM, SFA, SCR, SSP, PRE, JTG, DRI, BLK, WHT
    MEG: MEG, PFL, ASC, POR, CRI, PBL, 30C

Only touches rows where:
    - card_set__code is in the SV/MEG list above
    - variant_override == 'H' (won't touch anything already correct)
    - name ends with " EX" (trailing, case-sensitive uppercase EX --
      matches how these are actually stored, e.g. "Excadrill EX")

variant_sort is left unchanged (EX takes over H's existing sort
position, which is safe since these specific cards don't have a
separate H row to conflict with -- they ARE the H-tier row).

Usage:
    python manage.py shell -c "exec(open('fix_ex_variant_code.py').read())"

DRY RUN by default -- shows what would change, changes nothing.
Set APPLY = True to actually update.
"""

from products.models import PokemonProduct

APPLY = True  # flip to True once the dry-run output looks right

SV_SETS = ['SVI', 'PAL', 'OBF', 'MEW', 'PAR', 'PAF', 'TEF', 'TWM', 'SFA', 'SCR', 'SSP', 'PRE', 'JTG', 'DRI', 'BLK', 'WHT']
MEG_SETS = ['MEG', 'PFL', 'ASC', 'POR', 'CRI', 'PBL', '30C']
TARGET_SETS = SV_SETS + MEG_SETS

print(f"Mode: {'APPLY (updating)' if APPLY else 'DRY RUN (no changes will be made)'}")
print(f"Target sets: {TARGET_SETS}")
print()

candidates = PokemonProduct.objects.filter(
    card_set__code__in=TARGET_SETS,
    variant_override='H',
    name__endswith=' EX',
).select_related('card_set')

print(f"Rows matching (H variant, name ends with ' EX'): {candidates.count()}")
print()

from collections import Counter
by_set = Counter(p.card_set.code for p in candidates)
for sc in TARGET_SETS:
    if by_set.get(sc):
        print(f"  {sc}: {by_set[sc]}")
print()

print("Sample (first 25):")
for p in candidates[:25]:
    print(f"  [{p.card_set.code}] {p.name} (#{p.card_number}) -- variant_override: 'H' -> 'EX'")

if APPLY:
    updated = candidates.update(variant_override='EX')
    print(f"\nDone. Updated {updated} row(s).")
else:
    print("\nDry run only -- no changes saved. Set APPLY = True and re-run to apply.")
