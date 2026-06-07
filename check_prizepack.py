# check_prizepack.py
import csv
from collections import defaultdict

BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"

stamp_types = defaultdict(int)
is_stamped = defaultdict(int)
names = []

with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if row.get('set_code','').strip() == 'PRIZEPACK':
            stamp_types[row.get('stamp_type','').strip()] += 1
            is_stamped[row.get('is_stamped','').strip()] += 1
            if len(names) < 5:
                names.append(row.get('name',''))

print("PRIZEPACK in Bible CSV:")
print(f"  stamp_type breakdown: {dict(stamp_types)}")
print(f"  is_stamped breakdown: {dict(is_stamped)}")
print(f"  Examples: {names}")
