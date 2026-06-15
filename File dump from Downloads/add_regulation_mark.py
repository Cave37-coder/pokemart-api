"""
Add regulation_mark field to CardSet and populate it.
Run: python manage.py shell --command="exec(open('add_regulation_mark.py').read())"
"""
from django.db import connection

# Check if column exists
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='products_cardset' AND column_name='regulation_mark'
    """)
    exists = cursor.fetchone()

if not exists:
    print("Adding regulation_mark column to CardSet...")
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE products_cardset ADD COLUMN regulation_mark VARCHAR(5) DEFAULT ''")
    print("Column added")
else:
    print("Column already exists")

# Regulation mark mapping by set code
# Based on official Pokemon TCG regulation marks
MARK_MAP = {
    # Sword & Shield era (F mark - rotated)
    'SWSH01': 'F', 'SWSH02': 'F', 'SWSH03': 'F', 'SWSH04': 'F',
    'SWSH05': 'F', 'SWSH06': 'F', 'SWSH07': 'F', 'SWSH08': 'F',
    'SWSH09': 'F', 'SWSH10': 'F', 'SWSH11': 'F', 'SWSH12': 'F',
    'CRZ': 'F', 'PR-SWSH': 'F', 'SHF': 'F', 'SHFSV': 'F',
    'PGO': 'F', 'CEL': 'F', 'CLB': 'F', 'CCC': 'F',
    'CPA': 'F', 'MCD21': 'F', 'MCD22': 'F',
    'BST': 'F', 'ASRTG': 'F', 'BRSTG': 'F', 'LORTG': 'F',
    'SITTG': 'F', 'CRZGG': 'F', 'ST': 'F', 'TOT22': 'F',
    'PRIZEPACK': 'F',
    # Scarlet & Violet era (G mark - rotated Apr 10 2026)
    'SV1': 'G', 'SV2': 'G', 'SV3': 'G', 'SV4': 'G',
    'SV4PT5': 'G', 'SV5': 'G', 'SV6': 'G', 'SV6PT5': 'G',
    'SV7': 'G', 'SV8': 'G', 'SV8PT5': 'G',
    'PR-SV': 'G', 'SVEP': 'G', 'MEW': 'G',
    'MCD23': 'G', 'MCD24': 'G',
    # Mega Evolution era (H/I/J marks - LEGAL)
    'MEP': 'H',   # Pitch Black
    'ME1': 'H',   # Pitch Black
    'CRO': 'H',   # Chaos Rising
    'POR': 'H',   # Perfect Order
    'ASC': 'I',   # Ascended Heroes
    'PHF': 'I',   # Phantasmal Flames
    'MEG': 'I',   # Mega Evolution
    'MEE': 'I',   # Mega Evolution Energies
    'MEP2': 'I',  # Mega Evolution Promos
    'PRE': 'I',   # Prismatic Evolutions (reprint set)
    'BLK': 'J',   # Black Bolt
    'WHT': 'J',   # White Flair
    'DR': 'J',    # Destined Rivals
    'SJ': 'J',    # Surging Sparks (if in B9)
    'PR-ME': 'H', # ME Black Star Promos
}

# Update by set code
from products.models import CardSet
updated = 0
for code, mark in MARK_MAP.items():
    count = CardSet.objects.filter(code=code).update(regulation_mark=mark)
    if count > 0:
        updated += count
        print(f"  {code} → {mark}")

# All B8 sets get G mark if not already set
b8_count = CardSet.objects.filter(era__code='B8', regulation_mark='').update(regulation_mark='G')
if b8_count:
    print(f"  B8 remaining → G ({b8_count} sets)")

# All B7 sets get F mark if not already set  
b7_count = CardSet.objects.filter(era__code='B7', regulation_mark='').update(regulation_mark='F')
if b7_count:
    print(f"  B7 remaining → F ({b7_count} sets)")

# All B9 sets get H mark if not already set
b9_count = CardSet.objects.filter(era__code='B9', regulation_mark='').update(regulation_mark='H')
if b9_count:
    print(f"  B9 remaining → H ({b9_count} sets)")

print(f"\nTotal updated: {updated}")

# Show summary
from django.db.models import Count
summary = CardSet.objects.values('regulation_mark').annotate(count=Count('id')).order_by('regulation_mark')
print("\nRegulation mark summary:")
for s in summary:
    mark = s['regulation_mark'] or '(none)'
    legal = '✓ LEGAL' if s['regulation_mark'] in ['H','I','J'] else ('✗ rotated' if s['regulation_mark'] in ['F','G'] else 'Expanded only')
    print(f"  {mark}: {s['count']} sets — {legal}")
