"""
Find records with ASRTG pb_ids but wrong card_set
Run: python manage.py shell --command="exec(open('find_pbid_conflict.py').read())"
"""
from products.models import PokemonProduct

# Find all records with ASRTG- pb_ids
records = PokemonProduct.objects.filter(
    pb_id__startswith='ASRTG-'
).values('id', 'pb_id', 'card_set__code', 'card_set__name', 'tcgcsv_product_id', 'name')

print(f"Records with ASRTG- pb_id: {records.count()}")
for r in records[:20]:
    print(f"  id={r['id']} pb_id={r['pb_id']} set={r['card_set__code']} pid={r['tcgcsv_product_id']} {r['name'][:25]}")

# Also check other problem sets
for code in ['CRZGG', 'HIFSV', 'SHFSV', 'GENRC', 'LTRRC', 'ST', 'LORTG']:
    count = PokemonProduct.objects.filter(pb_id__startswith=f'{code}-').count()
    wrong_set = PokemonProduct.objects.filter(
        pb_id__startswith=f'{code}-'
    ).exclude(card_set__code=code).count()
    print(f"{code}: {count} with pb_id prefix, {wrong_set} with wrong card_set")
