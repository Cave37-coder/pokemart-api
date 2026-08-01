"""
diagnose_unreachable_card_keys.py

Michael, 2026-08-01: "how come i don't 100% on Broke Set or Base Set if i
have selected every card?????" -- CRI (Chaos Rising) sits at 93%/96% despite
every visible card being checked.

FIXED 2026-08-01 (v2): the first version of this script hand-reimplemented
the card-key grouping logic instead of calling the real function -- wrong,
and exactly the kind of drift Michael called out ("why is the script not
using the same logic?"). This version imports and calls
products.completion.get_set_card_map() directly -- the ACTUAL function the
checklist page, tier math, and leaderboard all use for card counts -- so
there is zero risk of the diagnostic disagreeing with production logic.
Also fixed: this checks EVERY eligible set unconditionally, no scoping.

What it looks for: get_set_card_map() only ever produces a key the
frontend can send ("{number}" or "{number}_{variant}", always plain
digits/digits like "007/086") when a display_num is shared by exactly ONE
distinct product name. The moment two DIFFERENT cards land on the same
display_num (most often: a product has a blank `number` field and its
zero-padded "{card_number}/{total_cards}" fallback happens to collide with
another card, or a manually-added product was never given a proper
`number`), the function disambiguates by appending "-{lowest product id}"
to the key so they don't merge internally. That key is correct math but
PHYSICALLY UNREACHABLE from the frontend -- the static checklist data and
the checkboxes only ever send the plain form. That card silently counts as
"required" forever and can never be checked off, capping every tier below
100% no matter what gets checked.

READ-ONLY -- calls the real get_set_card_map() (a pure read function) and
only prints. Changes nothing.

Usage:
    python manage.py shell -c "exec(open('diagnose_unreachable_card_keys.py').read())"
"""
import re

from products.models import CardSet, PokemonProduct
from products.completion import is_set_eligible, get_set_card_map

# Any key NOT of the plain "digits/digits" shape is a disambiguated,
# frontend-unreachable key (get_set_card_map() only ever appends a "-{id}"
# suffix in the collision case -- see module docstring).
PLAIN_KEY_RE = re.compile(r'^\d+/\d+$')

all_sets = list(CardSet.objects.all().order_by('code'))
checked_sets = [cs for cs in all_sets if is_set_eligible(cs)]
print(f"Checking ALL {len(checked_sets)} eligible sets (of {len(all_sets)} total) -- no scoping, no filtering.\n")

total_unreachable = 0
sets_with_issues = 0

for cs in checked_sets:
    card_map = get_set_card_map(cs)  # <-- the REAL function, same one the site uses
    if not card_map:
        continue

    bad_keys = [k for k in card_map if not PLAIN_KEY_RE.match(k)]
    if not bad_keys:
        continue

    sets_with_issues += 1
    print(f"[{cs.code}] {cs.name} (total_cards={cs.total_cards}): {len(bad_keys)} unreachable key(s)")
    for key in bad_keys:
        entry = card_map[key]
        card_number = entry["card_number"]
        variants = sorted(entry["variants"])
        # Look up every active product for this card_number in this set so
        # we can show Michael exactly which products are colliding.
        rows = list(
            PokemonProduct.objects
            .filter(card_set=cs, is_active=True, card_number=card_number)
            .values("id", "name", "number", "variant_override")
        )
        print(f"    key={key!r} (card_number={card_number}, variants={variants}) -- frontend can never generate this exact key.")
        for r in rows:
            print(f"        id={r['id']} name={r['name']!r} number={r['number']!r} variant_override={r['variant_override']!r}")
        total_unreachable += 1
    print()

print(f"Done. {total_unreachable} unreachable key(s) found across {sets_with_issues} set(s) (out of {len(checked_sets)} checked).")
if total_unreachable == 0:
    print("Nothing found via this check -- the 93%/96% on CRI has a different cause, needs another angle.")
