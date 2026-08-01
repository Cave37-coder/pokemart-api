"""
diagnose_total_cards_mismatches.py

Root cause for Crown Zenith (CRZ) not registering as Master Set complete
even with every card checked (Michael, 2026-08-01): CRZ's total_cards is
294 in the DB, but its own `number` field on every product (e.g.
"052/159") shows the real card count is 159. 294 looks like it was
populated from a raw product-ROW count (which includes every N/H/RH
variant row separately) instead of the actual number of distinct cards.

Why that breaks Master Set specifically: get_set_card_map() only falls
back to a "{card_number}/{total_cards}" computed key when a product's own
`number` field is blank -- and CRZ has ~20 H/RH rows with a blank
`number`. With total_cards wrong, that fallback produces a DIFFERENT
string ("150/294") than the one already used by that same card's OTHER
variant rows ("150/159", straight from their own populated `number`
field). That splits one physical card into two separate card_map entries
-- and the frontend's static checklist data only ever generates the
correct "150/159" key, so the "150/294" one can never be satisfied no
matter what's checked. Master Set requires every card in the set, so it
can never hit 100%.

It also distorts the lower tiers more subtly: `numbered = [c for c in
card_map if c.card_number <= total_cards]` -- an inflated total_cards
drags genuine "extra"/secret cards (meant to count ONLY toward Master
Set) into Broke Base / Base Set / Special Set Base too, overstating what
those tiers require.

This isn't unique to CRZ -- ASC was already flagged with the same class of
issue (total_cards=728, should be ~217). This script checks EVERY set,
not just those two, so we get the full picture in one pass instead of
guessing set-by-set.

Heuristic: the correct total_cards for a set is the most common ("mode")
denominator among that set's own populated `number` fields -- regular
numbered cards overwhelmingly share one denominator; only a handful of
secret/promo cards are numbered above it. A mismatch is only reported if
the mode covers a healthy majority of populated numbers, so a few stray
bad data points don't trigger a false positive.

DRY RUN by default -- prints every mismatch found, changes NOTHING.
Set APPLY = True and re-run once the printed list looks right to actually
save the fixes.

Usage:
    python manage.py shell -c "exec(open('diagnose_total_cards_mismatches.py').read())"
"""
import re
from collections import Counter

from products.models import CardSet, PokemonProduct

APPLY = True  # flip to True once the printed list below looks right

NUMBER_RE = re.compile(r'^\d+/(\d+)$')
MIN_CONFIDENCE = 0.60  # require the mode to cover at least this fraction
                        # of a set's populated numbers before we trust it
# RESULTS REVIEWED with Michael 2026-08-01: first run flagged 131/198 sets,
# with CRZ (159) and ASC (217) landing exactly on the values already
# confirmed correct earlier -- strong evidence the heuristic is sound. Three
# entries (DET, MEP, SMP) only had 1-4 populated `number` values though --
# not enough of a sample to trust a "mode" from, so those need a human
# look rather than an auto-fix. Raising the bar here instead of trusting
# MIN_CONFIDENCE alone, since 1/1 = 100% "confidence" is meaningless noise.
MIN_SAMPLE = 10  # a set needs at least this many populated `number`
                  # values before we'll trust a mismatch verdict at all

print(f"Mode: {'APPLY (fixing)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

all_sets = list(CardSet.objects.all().order_by('code'))
mismatches = []
low_sample = []  # flagged but not enough data to trust -- needs a human look

for cs in all_sets:
    numbers = list(
        PokemonProduct.objects
        .filter(card_set=cs, is_active=True)
        .exclude(number='')
        .values_list('number', flat=True)
    )
    denominators = [int(m.group(1)) for m in (NUMBER_RE.match((n or '').strip()) for n in numbers) if m]
    if not denominators:
        continue  # set has no populated `number` fields at all -- can't check it this way

    mode_denom, mode_count = Counter(denominators).most_common(1)[0]
    confidence = mode_count / len(denominators)
    if cs.total_cards == mode_denom or confidence < MIN_CONFIDENCE:
        continue
    if len(denominators) < MIN_SAMPLE:
        low_sample.append((cs, mode_denom, confidence, len(denominators)))
    else:
        mismatches.append((cs, mode_denom, confidence, len(denominators)))

print(f"Checked {len(all_sets)} sets.")
print(f"Found {len(mismatches)} with a likely total_cards mismatch (sample size >= {MIN_SAMPLE}, will be auto-fixed if APPLY=True):\n")
for cs, mode_denom, confidence, n in mismatches:
    print(f"  [{cs.code}] {cs.name}: total_cards={cs.total_cards} -> should probably be {mode_denom} "
          f"(confidence {confidence:.0%} of {n} populated `number` values)")

if low_sample:
    print(f"\n{len(low_sample)} more flagged but with too few populated `number` values to trust automatically "
          f"(NOT touched even if APPLY=True -- review manually):")
    for cs, mode_denom, confidence, n in low_sample:
        print(f"  [{cs.code}] {cs.name}: total_cards={cs.total_cards} -> maybe {mode_denom}? "
              f"(only {n} populated `number` value(s) to go on)")

if not mismatches:
    print("\nNothing to fix.")
elif APPLY:
    print("\nApplying fixes...")
    for cs, mode_denom, confidence, n in mismatches:
        cs.total_cards = mode_denom
        cs.save(update_fields=['total_cards'])
    print(f"Fixed {len(mismatches)} set(s). Re-run with APPLY = False to confirm zero mismatches remain.")
else:
    print("\nDry run only -- no changes saved. Review the list above, then set APPLY = True and re-run to apply.")
