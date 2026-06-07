# check_bible_set_codes.py
import csv
from collections import defaultdict

BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"

counts = defaultdict(int)
with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        counts[row.get('set_code','').strip()] += 1

print(f"{'SET_CODE':<14} {'CARDS'}")
print("-" * 25)
for code, count in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"{code:<14} {count}")
