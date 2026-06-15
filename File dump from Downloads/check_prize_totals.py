# Check what card totals appear in the PRIZEPACK CSV rows
# The /XXX in card numbers tells us the source set
import csv
from collections import Counter

CSV_PATH = r'pokebulk_cards_20260524_1558.csv'
totals = Counter()

with open(CSV_PATH, encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) < 8 or row[2].strip() != 'PRIZEPACK':
            continue
        card_num_raw = row[7].strip()
        if '/' in card_num_raw:
            total = card_num_raw.split('/')[1].strip()
            totals[total] += 1

print("Card total counts (source set indicators):")
for total, count in sorted(totals.items(), key=lambda x: -x[1]):
    print(f"  /{total}: {count} cards")
