"""
backfill_missing_completion_events.py

Root cause (Michael, 2026-08-01): SetCompletionEvent rows -- the ONLY thing
the Wall of Honour and the Checklists Overview tile highlight actually
read -- are only ever created inside checklist_toggle, at the exact moment
a NEW checked card pushes a tier over 100%. They are never created
retroactively.

Michael had already fully checked Crown Zenith (CRZ), ASC, CRI and PBL
base sets BEFORE diagnose_total_cards_mismatches.py corrected those sets'
total_cards. That fix made the tiers mathematically complete, but no new
checklist_toggle call happened afterward to fire the event -- so Wall of
Honour and the tile highlights never picked them up, even though the live
completion math (same math used by the set's own checklist page, and the
leaderboard's "Complete" badge) has shown them as done all along.

This is a one-off backfill: for every (user, set) pair the user has ANY
checked cards in, recompute completion live and create any missing
SetCompletionEvent rows for tiers that are already complete. Uses
get_or_create, same as checklist_toggle does -- safe to re-run, never
duplicates, never touches an existing event's completed_at.

Only checks (user, set) pairs with at least one checked card -- if a user
has zero checked cards in a set, no tier can possibly be complete, so
there's nothing to gain from checking every user against all ~146 sets.

DRY RUN by default -- prints every backfill it WOULD create, changes
nothing. Set APPLY = True and re-run once the printed list looks right.

Usage:
    python manage.py shell -c "exec(open('backfill_missing_completion_events.py').read())"
"""
from collections import defaultdict

from django.contrib.auth import get_user_model
from products.models import ChecklistEntry, CardSet, SetCompletionEvent
from products.completion import is_set_eligible, compute_user_set_completion, TIER_LABELS

APPLY = False  # flip to True once the printed list below looks right

User = get_user_model()

print(f"Mode: {'APPLY (fixing)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

# Only (user, set) pairs with at least one checked card -- see module
# docstring for why this is safe to skip everything else.
pairs = ChecklistEntry.objects.values_list('user_id', 'card_set').distinct()
pairs_by_user = defaultdict(set)
for user_id, card_set in pairs:
    pairs_by_user[user_id].add(card_set)

all_set_codes = {code for codes in pairs_by_user.values() for code in codes}
sets_by_code = {cs.code: cs for cs in CardSet.objects.filter(code__in=all_set_codes)}
users_by_id = {u.id: u for u in User.objects.filter(id__in=pairs_by_user.keys())}

existing_events = set(SetCompletionEvent.objects.values_list('user_id', 'card_set', 'tier'))

to_create = []  # [(user, card_set, tier_key), ...]

for user_id, set_codes in pairs_by_user.items():
    user = users_by_id.get(user_id)
    if not user:
        continue
    for code in set_codes:
        cs = sets_by_code.get(code)
        if not cs or not is_set_eligible(cs):
            continue
        result = compute_user_set_completion(user, cs)
        for tier_key, data in result['tiers'].items():
            if data['complete'] and (user_id, code, tier_key) not in existing_events:
                to_create.append((user, cs, tier_key))

print(f"Checked {len(pairs_by_user)} user(s) across {len(all_set_codes)} set(s) with checklist activity.")
print(f"Found {len(to_create)} completed tier(s) missing a SetCompletionEvent:\n")
for user, cs, tier_key in to_create:
    label = TIER_LABELS.get(tier_key, tier_key)
    print(f"  {user.username} -- [{cs.code}] {cs.name}: {label}")

if not to_create:
    print("\nNothing to backfill.")
elif APPLY:
    print("\nCreating events...")
    for user, cs, tier_key in to_create:
        SetCompletionEvent.objects.get_or_create(user=user, card_set=cs.code, tier=tier_key)
    print(f"Created {len(to_create)} event(s). Re-run with APPLY = False to confirm zero remain missing.")
else:
    print("\nDry run only -- no changes saved. Review the list above, then set APPLY = True and re-run to apply.")
