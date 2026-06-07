# check_pps_and_tg.py
import csv, os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from collections import defaultdict

BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"

# Check Prize Pack cards in DB - what series info is stored
print("PRIZE PACK IN DB:")
pp_cards = PokemonProduct.objects.filter(
    card_set__code='PRIZEPACK'
).values('name', 'card_number', 'pb_id', 'tcgcsv_product_id')[:10]
for p in pp_cards:
    print(f"  #{p['card_number']} {p['name'][:30]} pb_id={p['pb_id'][:30]}")

# Check Bible for any series info in PRIZEPACK cards
print("\nPRIZE PACK IN BIBLE - checking for series fields:")
with open(BIBLE, encoding='utf-8') as f:
    count = 0
    for row in csv.DictReader(f):
        if row.get('set_code','').strip() == 'PRIZEPACK' and count < 3:
            print(f"  Fields: {dict(row)}")
            count += 1
            break

# Check which TG sets exist in DB and their records
print("\nTRAINER GALLERY SETS IN DB:")
tg_codes = ['BST','BRSTG','ASRTG','LORTG','SITTG','ST','CRZGG']
from products.models import CardSet
from django.db.models import Count
for code in tg_codes:
    try:
        s = CardSet.objects.get(code=code)
        count = PokemonProduct.objects.filter(card_set=s).count()
        print(f"  {code:<10} {count:>4} records  {s.name}")
    except CardSet.DoesNotExist:
        print(f"  {code:<10} NOT IN DB")

# Check Bible for TG sets
print("\nTRAINER GALLERY IN BIBLE:")
bible_tg = defaultdict(int)
with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        code = row.get('set_code','').strip()
        if any(tg in code for tg in ['TG','BST','BRSTG','ASRTG','LORTG','SITTG']):
            bible_tg[code] += 1
for code, count in sorted(bible_tg.items()):
    print(f"  {code:<12} {count} cards in Bible")
