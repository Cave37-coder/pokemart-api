"""
fix_meg_null_cardnumbers.py
For ALL MEG era sets — finds records with null card_number,
matches to sibling by tcgcsv_product_id, copies card_number across.
Run with DATABASE_URL uncommented in .env
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from collections import defaultdict

MEG_SETS = ['MEG', 'PFL', 'ASC', 'POR', 'CRI', 'PBL']

total_fixed = 0

for set_code in MEG_SETS:
    all_records = list(PokemonProduct.objects.filter(
        card_set__code=set_code
    ).values('id', 'tcgcsv_product_id', 'card_number', 'variant_override', 'name'))

    if not all_records:
        continue

    # Group by tcgcsv_product_id
    by_pid = defaultdict(list)
    for p in all_records:
        if p['tcgcsv_product_id']:
            by_pid[p['tcgcsv_product_id']].append(p)

    null_count = sum(1 for p in all_records if p['card_number'] is None)
    print(f"\n{set_code}: {len(all_records)} records, {null_count} with null card_number")

    to_fix = []
    for pid, records in by_pid.items():
        known_num = next((r['card_number'] for r in records if r['card_number'] is not None), None)
        if known_num is None:
            continue
        for r in records:
            if r['card_number'] is None:
                to_fix.append((r['id'], known_num))

    if to_fix:
        for rec_id, num in to_fix:
            PokemonProduct.objects.filter(id=rec_id).update(card_number=num)
        print(f"  Fixed {len(to_fix)} records")
        total_fixed += len(to_fix)
    else:
        print(f"  Nothing to fix")

print(f"\nTotal fixed: {total_fixed}")
