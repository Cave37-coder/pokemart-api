"""
fix_asc_pattern_variant_tagging.py

Michael, 2026-08-01: "ASC was plugged Energy Pattern Holo as RH, don't
understand why it was done that way... add ESH to variants and correct
it." Confirmed via diagnose_unreachable_card_keys.py that ASC's "(Energy
Symbol Pattern)" products, and a smaller number of "(Team Rocket)"
products, are both stored with variant_override='RH' -- the same code as
plain reverse holo, and the same class of bug as the ball-variant
mistagging fixed earlier this session.

This alone wasn't the full story though: products/completion.py's
get_set_card_map() was ALSO fixed today (v2) to stop treating same-card
print variants as different physical cards just because their product
names differ (e.g. "Camerupt" vs "Camerupt (Energy Symbol Pattern)").
Retagging without that fix would have accomplished nothing -- the cards
would still fragment into unreachable keys. Both fixes are needed
together, which is why this runs after the get_set_card_map() change is
deployed.

Two retags, both driven by the "(X)" suffix already present in the
product name (trusted the same way the ball-variant fix trusted it):
  - "(Energy Symbol Pattern)" -> ESH (new code, added to
    products/completion.py PATTERN_VARIANTS -- counts toward Special Set
    Base / Master Set, same scope as ball variants)
  - "(Team Rocket)" -> TR (an EXISTING code that was simply never applied
    correctly -- TR already sits outside FULL_VARIANTS, i.e. it's a bonus
    pull that never gates any tier, by original design)

Checks EVERY set, not just ASC, in case the same import pattern hit
others.

DRY RUN by default -- prints every mismatch found, changes NOTHING.
Set APPLY = True and re-run once the printed list looks right.

Usage:
    python manage.py shell -c "exec(open('fix_asc_pattern_variant_tagging.py').read())"
"""
import re
from collections import defaultdict

from products.models import PokemonProduct

APPLY = False  # flip to True once the printed list below looks right

PATTERN_NAME_TO_CODE = {
    "Energy Symbol Pattern": "ESH",
    "Team Rocket": "TR",
}
NAME_RE = re.compile(r'\((' + '|'.join(re.escape(k) for k in PATTERN_NAME_TO_CODE) + r')\)')

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
    correct_code = PATTERN_NAME_TO_CODE[m.group(1)]
    if (p.variant_override or '').strip() != correct_code:
        mismatches.append((p, correct_code))

by_set = defaultdict(list)
for p, correct_code in mismatches:
    by_set[p.card_set.code].append((p, correct_code))

print(f"Checked {len(candidates)} active products with a set assigned.")
print(f"Found {len(mismatches)} pattern-variant product(s) with the wrong variant_override, across {len(by_set)} set(s):\n")
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
