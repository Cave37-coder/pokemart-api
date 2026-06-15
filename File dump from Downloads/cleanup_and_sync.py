"""
Clean up test records and properly sync all empty sets
Run: python manage.py shell --command="exec(open('cleanup_and_sync.py').read())"
"""
import subprocess
import sys
from products.models import PokemonProduct

# Clean up any partial test records for problem sets
SETS_TO_FIX = [
    'ASRTG', 'CRZGG', 'HIFSV', 'SHFSV', 'GENRC', 'LTRRC', 'ST', 'LORTG',
    'DEP', 'RUM', 'MEE', 'MEP', 'PR-NB', 'PR-WB', 'PR-BEST', 'PR-DP',
    'PR-SWSH', 'PRIZEPACK', 'TCGCL', 'TOT22', 'TOT23', 'TOT24',
    'MCD23', 'MCD24',
]

print("Cleaning up partial records...")
for code in SETS_TO_FIX:
    count = PokemonProduct.objects.filter(card_set__code=code).count()
    if count > 0:
        print(f"  {code}: deleting {count} partial records")
        PokemonProduct.objects.filter(card_set__code=code, stock=0).delete()

print("\nSyncing all empty sets...")
for code in SETS_TO_FIX:
    result = subprocess.run(
        [sys.executable, 'manage.py', 'sync_tcgcsv', '--set-code', code],
        capture_output=True, text=True
    )
    lines = (result.stdout + result.stderr).strip().split('\n')
    # Find the created= line
    summary = next((l for l in lines if 'created=' in l), lines[-1])
    count_after = PokemonProduct.objects.filter(card_set__code=code).count()
    print(f"  {code}: {summary.strip()} | DB now={count_after}")

print("\nDone!")
