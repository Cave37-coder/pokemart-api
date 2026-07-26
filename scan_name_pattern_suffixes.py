import re
from collections import Counter

from products.models import PokemonProduct

PATTERN_SUFFIX_RE = re.compile(r'\s*\(([^)]+)\)\s*$')

qs = PokemonProduct.objects.exclude(name__isnull=True).only(
    'id', 'name', 'variant_override', 'card_set_id'
).select_related('card_set')

total = qs.count()
matched = []

print(f"Scanning {total} products for trailing '(...)' suffixes...")
print("-" * 70)

for i, p in enumerate(qs.iterator(), 1):
    m = PATTERN_SUFFIX_RE.search(p.name or '')
    if m:
        matched.append((p.id, p.name, p.variant_override, p.card_set.code if p.card_set else '??'))
    if i % 1000 == 0:
        print(f"...scanned {i}/{total}")

print("-" * 70)
print(f"Total matches: {len(matched)}")
print("-" * 70)

# Breakdown by which pattern text appears, and by set + variant_override,
# so it's easy to spot anything that ISN'T a real ASC-style stamp pattern.
pattern_counts = Counter()
set_variant_counts = Counter()

for pid, name, var, set_code in matched:
    m = PATTERN_SUFFIX_RE.search(name)
    pattern_text = m.group(1).strip()
    pattern_counts[pattern_text] += 1
    set_variant_counts[(set_code, var)] += 1

print("Breakdown by extracted pattern text:")
for pattern_text, count in pattern_counts.most_common():
    print(f"  {count:4d}  {pattern_text!r}")

print()
print("Breakdown by (card_set, variant_override):")
for (set_code, var), count in sorted(set_variant_counts.items(), key=lambda x: -x[1]):
    print(f"  {count:4d}  set={set_code:10s} variant_override={var}")

print()
print("Full list of matches (id, name, variant_override, set_code):")
print("-" * 70)
for pid, name, var, set_code in matched:
    print(f"{pid:8d}  [{set_code:8s}] {var or '-':4s}  {name}")
