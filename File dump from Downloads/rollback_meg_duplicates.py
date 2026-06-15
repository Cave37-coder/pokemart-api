"""
rollback_meg_duplicates.py
Deletes the wrongly created TCGCSV-{pid}-{vo} records for MEG era sets.
These were created by sync_meg_variants_prices.py and are duplicates
of the correct Bible CSV records already in the DB.
Run with DATABASE_URL uncommented in .env
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct

MEG_SETS = ['MEG', 'PFL', 'ASC', 'POR', 'CRI']

total_deleted = 0

for set_code in MEG_SETS:
    # These are the wrongly created records — pb_id ends with -N, -H, or -RH
    # and was created by sync_meg_variants_prices.py
    bad_records = PokemonProduct.objects.filter(
        card_set__code=set_code,
        pb_id__regex=r'^TCGCSV-\d+-[NHR]'
    )
    count = bad_records.count()
    print(f"{set_code}: {count} duplicate records to delete")
    for p in bad_records[:5]:
        print(f"  {p.pb_id} | #{p.card_number} | {p.variant_override} | {p.name[:40]}")
    bad_records.delete()
    total_deleted += count

print(f"\nTotal deleted: {total_deleted}")
print("Done. DB restored to Bible CSV state.")
