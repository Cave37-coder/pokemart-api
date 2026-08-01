"""
fix_ball_variant_tagging.py

Root cause (Michael, 2026-08-01 -- spotted after the tier tabs shipped:
ASC's Special Set Base tab showed the EXACT same owned/required numbers as
Base Set, 115/535 both, which is impossible if the set actually has ball
variants -- Special Set Base always requires Base Set's variants PLUS every
ball variant, so it must need strictly MORE whenever ball reprints exist).

Confirmed via the live API: every "(Poke Ball)" product in ASC is stored
with variant_override="RH" instead of "PB". The frontend's own card badges
already show "PB" correctly (built from a separate, correctly-derived data
source), but products/completion.py's get_set_card_map() only ever trusts
PokemonProduct.variant_override -- never the product name -- so a
ball-variant row mistagged "RH" silently collapses into the ordinary
reverse-holo slot instead of adding its own ball-specific requirement.
That's why Special Set Base and Master Set undercount for every set with
this mistagging: the ball requirement, and any checked-off progress toward
it, is invisible to the tier math entirely.

This was flagged earlier in the project (ASC's ball-variant products) but
never actually fixed -- this script fixes it properly, and checks EVERY
set, not just ASC, in case the same import issue hit others.

Detects the correct code from the "(X Ball)" suffix already present in the
product name (this suffix is trusted -- it's how the site distinguishes
these variants in the first place) and compares it against the stored
variant_override. Only touches rows where the two disagree.

DRY RUN by default -- prints every mismatch found, changes NOTHING.
Set APPLY = True and re-run once the printed list looks right.

Usage:
    python manage.py shell -c "exec(open('fix_ball_variant_tagging.py').read())"
"""
import re
from collections import defaultdict

from products.models import PokemonProduct

APPLY = False  # flip to True once the printed list below looks right

# Matches BALL_VARIANTS in products/completion.py exactly -- do not add
# codes that aren't in that set, they'd never be recognised by the tier
# math anyway.
BALL_NAME_TO_CODE = {
    "Poke Ball": "PB",
    "Master Ball": "MB",
    "Love Ball": "LB",
    "Friend Ball": "FB",
    "Quick Ball": "QB",
    "Ultra Ball": "UB",
    "Dusk Ball": "DB",
}
NAME_RE = re.compile(r'\((' + '|'.join(re.escape(k) for k in BALL_NAME_TO_CODE) + r')\)')

print(f"Mode: {'APPLY (fixing)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

candidates = (
    PokemonProduct.objects
    .filter(is_active=True)
    .exclude(card_set__isnull=True)
    .select_related('card_set')
)

mismatches = []  # [(product, correct_code), ...]
for p in candidates:
    m = NAME_RE.search(p.name or '')
    if not m:
        continue
    correct_code = BALL_NAME_TO_CODE[m.group(1)]
    if (p.variant_override or '').strip() != correct_code:
        mismatches.append((p, correct_code))

by_set = defaultdict(list)
for p, correct_code in mismatches:
    by_set[p.card_set.code].append((p, correct_code))

print(f"Checked {len(candidates)} active products with a set assigned.")
print(f"Found {len(mismatches)} ball-variant product(s) with the wrong variant_override, across {len(by_set)} set(s):\n")
for set_code, rows in sorted(by_set.items()):
    cs_name = rows[0][0].card_set.name
    print(f"  [{set_code}] {cs_name}: {len(rows)} product(s)")
    for p, correct_code in rows[:5]:
        print(f"      {p.name}: variant_override={p.variant_override!r} -> should be {correct_code!r}")
    if len(rows) > 5:
        print(f"      ...and {len(rows) - 5} more")

if not mismatches:
    print("\nNothing to fix.")
elif APPLY:
    print("\nApplying fixes...")
    for p, correct_code in mismatches:
        p.variant_override = correct_code
        p.save(update_fields=['variant_override'])
    print(f"Fixed {len(mismatches)} product(s). Re-run with APPLY = False to confirm zero mismatches remain.")
else:
    print("\nDry run only -- no changes saved. Review the list above, then set APPLY = True and re-run to apply.")
