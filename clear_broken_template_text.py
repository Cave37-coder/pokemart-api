"""
clear_broken_template_text.py

Companion to audit_broken_template_text.py. Blanks out ONLY the specific
fields that contain the confirmed "{{" truncation corruption -- 677 rows
across BLK/WHT/MEG/ASC/PFL/CRI/POR as of 2026-07-14. Leaves every other
field on each row (name, price, stock, HP, weakness, etc.) completely
untouched -- this only clears attack_1_text/attack_2_text/ability_text/
description, and only on the specific field(s) that actually contain the
corruption on each row (e.g. if only attack_2_text is broken,
attack_1_text is left alone even if it has real data).

After running this, use enrich_serebii.py to re-populate the cleared
fields with correct text (only fills blanks, so this clearing step is a
required precondition).

Usage:
    python manage.py shell -c "exec(open('clear_broken_template_text.py').read())"

DRY RUN by default -- shows what would be cleared, changes nothing.
Set APPLY = True to actually clear.
"""

from products.models import PokemonProduct
from django.db.models import Q
from django.db import transaction

APPLY = True  # flip to True once the dry-run output looks right

TEXT_FIELDS = ['attack_1_text', 'attack_2_text', 'ability_text', 'description']

print(f"Mode: {'APPLY (clearing)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

query = Q()
for field in TEXT_FIELDS:
    query |= Q(**{f'{field}__icontains': '{{'})

affected = list(PokemonProduct.objects.filter(query).select_related('card_set'))
print(f"Rows with corrupted text: {len(affected)}")
print()

from collections import Counter
by_set = Counter(p.card_set.code if p.card_set else 'NO_SET' for p in affected)
for sc, count in by_set.most_common():
    print(f"  {sc}: {count}")
print()

to_update = []
field_clear_count = Counter()

for p in affected:
    changed = False
    for field in TEXT_FIELDS:
        val = getattr(p, field) or ''
        if '{{' in val:
            setattr(p, field, '')
            field_clear_count[field] += 1
            changed = True
    if changed:
        to_update.append(p)

print("Fields being cleared (count):")
for field, count in field_clear_count.items():
    print(f"  {field}: {count}")
print()

if APPLY and to_update:
    with transaction.atomic():
        PokemonProduct.objects.bulk_update(to_update, TEXT_FIELDS, batch_size=500)
    print(f"Done. Cleared corrupted fields on {len(to_update)} row(s).")
    print("Next step: re-run enrich_serebii.py on each affected set to backfill correct text.")
elif to_update:
    print("Dry run only -- no changes saved. Set APPLY = True and re-run to apply.")
else:
    print("Nothing to clear.")
