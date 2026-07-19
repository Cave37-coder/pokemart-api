"""
audit_broken_template_text.py
Read-only audit -- searches EVERY text field that could carry this same
corruption (attack_1_text, attack_2_text, ability_text, description) for
literal "{{" template syntax, confirmed present in at least one Chaos
Rising card's attack_1_text. Determines how widespread this is before
deciding on a fix.

Usage:
    python manage.py shell -c "exec(open('audit_broken_template_text.py').read())"
"""

from products.models import PokemonProduct
from django.db.models import Q

TEXT_FIELDS = ['attack_1_text', 'attack_2_text', 'ability_text', 'description']

query = Q()
for field in TEXT_FIELDS:
    query |= Q(**{f'{field}__icontains': '{{'})

affected = PokemonProduct.objects.filter(query).select_related('card_set')

print(f"Rows with '{{{{' in any text field: {affected.count()}")
print()

from collections import Counter
by_set = Counter(p.card_set.code if p.card_set else 'NO_SET' for p in affected)
print("Breakdown by set:")
for sc, count in by_set.most_common():
    print(f"  {sc}: {count}")
print()

print("Sample (first 25):")
for p in affected[:25]:
    broken_fields = [f for f in TEXT_FIELDS if '{{' in (getattr(p, f) or '')]
    print(f"  [{p.card_set.code if p.card_set else '?'}] {p.name} (id={p.id}, sku={p.sku}) -- broken: {broken_fields}")
    for f in broken_fields:
        val = getattr(p, f)
        print(f"    {f}: {val!r} (len={len(val)})")
