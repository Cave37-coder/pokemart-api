import csv
from collections import defaultdict

BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"

EMPTY_SETS = [
    "PR-BLW","LTRRC","PR-DPP","POP6","POP7","POP8","POP9","RUM",
    "TK1A","TK1B","POP2","POP3","TK2A","TK2B","POP4","POP5",
    "PR-HS","CL","PBL","PPS1","PPS2","PPS3","PPS4","PPS5","PPS6","PPS7","PPS8",
    "MCD11","MCD12","MCD15","MCD17","MCD19","MCD23",
    "PR-SM","SUM","GRI","BUS","SLG","CIN","UPR","FLI","MCD18",
    "LOT","TEU","DET","UNB","UNM","CEC",
    "PR-SV","SV1","SV2","SV3","SV3PT5","TCGCL","SV4","SV4PT5","MCD24",
    "PR-SWSH","CPA","MCD21","BRSTG","MCD22","SITTG",
    "TOT22","TOT23","TOT24",
    "PR-WB","B2","BP","PR-NP","POP1","RU1","PR-BEST",
    "PR-XY","MCD14","MCD16","GENRC",
]

print("Reading Bible CSV...")
bible_counts = defaultdict(int)
bible_examples = defaultdict(list)

with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        code = row.get('set_code', '').strip()
        name = row.get('name', '').strip()
        bible_counts[code] += 1
        if len(bible_examples[code]) < 2:
            bible_examples[code].append(name)

print(f"Bible CSV has {len(bible_counts)} unique set codes\n")
print(f"{'SET_CODE':<14} {'BIBLE_CARDS':<14} {'STATUS'}")
print("-" * 60)

in_bible = []
not_in_bible = []

for code in sorted(EMPTY_SETS):
    count = bible_counts.get(code, 0)
    examples = ', '.join(bible_examples.get(code, []))
    if count > 0:
        in_bible.append((code, count, examples))
        print(f"{code:<14} {count:<14} IN BIBLE - NOT IMPORTED | {examples[:50]}")
    else:
        not_in_bible.append(code)
        print(f"{code:<14} {count:<14} NOT IN BIBLE")

print()
print("=" * 60)
print(f"\nIN BIBLE but 0 in DB ({len(in_bible)}):")
for code, count, ex in sorted(in_bible, key=lambda x: -x[1]):
    print(f"  {code:<14} {count} cards - e.g. {ex[:50]}")

print(f"\nNOT IN BIBLE ({len(not_in_bible)}):")
print(f"  {', '.join(sorted(not_in_bible))}")
