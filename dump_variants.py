"""
dump_variants.py
Reads Bible CSV and extracts all unique variant values with counts and examples.
Run: python dump_variants.py
"""
import csv
from collections import defaultdict

BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"

variants = defaultdict(lambda: {'count': 0, 'examples': []})
card_types = defaultdict(lambda: {'count': 0, 'examples': []})
is_stamped = defaultdict(int)
stamp_types = defaultdict(int)

with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        v = row.get('variant', '').strip()
        ct = row.get('card_type', '').strip()
        st = row.get('is_stamped', '').strip()
        stype = row.get('stamp_type', '').strip()
        name = row.get('name', '').strip()
        set_code = row.get('set_code', '').strip()

        variants[v]['count'] += 1
        if len(variants[v]['examples']) < 3:
            variants[v]['examples'].append(f"{set_code}: {name}")

        card_types[ct]['count'] += 1
        if len(card_types[ct]['examples']) < 2:
            card_types[ct]['examples'].append(f"{set_code}: {name}")

        is_stamped[st] += 1
        if stype:
            stamp_types[stype] += 1

print("=" * 70)
print("ALL VARIANT VALUES IN BIBLE CSV")
print("=" * 70)
for v, data in sorted(variants.items(), key=lambda x: -x[1]['count']):
    print(f"\n  '{v}' -- {data['count']} cards")
    for ex in data['examples']:
        print(f"    e.g. {ex}")

print()
print("=" * 70)
print("ALL CARD TYPES IN BIBLE CSV")
print("=" * 70)
for ct, data in sorted(card_types.items(), key=lambda x: -x[1]['count']):
    print(f"\n  '{ct}' -- {data['count']} cards")
    for ex in data['examples']:
        print(f"    e.g. {ex}")

print()
print("=" * 70)
print("IS_STAMPED VALUES")
print("=" * 70)
for k, v in sorted(is_stamped.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print()
print("=" * 70)
print("STAMP_TYPE VALUES")
print("=" * 70)
for k, v in sorted(stamp_types.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print()
print("=" * 70)
print("CODE CARD EXAMPLES (card_type contains code)")
print("=" * 70)
with open(BIBLE, encoding='utf-8') as f:
    count = 0
    for row in csv.DictReader(f):
        ct = row.get('card_type', '').strip()
        if 'code' in ct.lower():
            count += 1
            if count <= 20:
                print(f"  {row['set_code']} | {row['name']} | variant={row['variant']} | type={ct} | price={row['pokebulk_zar']}")
print(f"Total code cards: {count}")
