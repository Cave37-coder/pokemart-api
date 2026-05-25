"""
Sync all missing/empty sets into DB
Run: python manage.py sync_tcgcsv --set-code SETCODE for each
Or run this script directly.
Run: python manage.py shell --command="exec(open('sync_missing_sets.py').read())"
"""
import subprocess
import sys

# All sets that need syncing
MISSING_CARDSET = ['DEP', 'GENRC', 'LTRRC', 'PR-BEST', 'PR-DP', 'PR-SWSH', 'RUM']
NO_PRODUCTS = [
    'ASRTG', 'CRZGG', 'HIFSV', 'LORTG', 'MCD23', 'MCD24', 'MEE', 'MEP',
    'PR-NB', 'PR-WB', 'PRIZEPACK', 'SHFSV', 'ST', 'TCGCL',
    'TOT22', 'TOT23', 'TOT24',
]
LOW_COUNT = ['SVE']

ALL_TO_SYNC = MISSING_CARDSET + NO_PRODUCTS + LOW_COUNT

print(f"Sets to sync: {len(ALL_TO_SYNC)}")
print(ALL_TO_SYNC)
print()

for code in ALL_TO_SYNC:
    print(f"Syncing {code}...", flush=True)
    result = subprocess.run(
        [sys.executable, 'manage.py', 'sync_tcgcsv', '--set-code', code],
        capture_output=True, text=True
    )
    # Print last few lines of output
    lines = (result.stdout + result.stderr).strip().split('\n')
    for line in lines[-4:]:
        if line.strip():
            print(f"  {line}")
    print()

print("All done!")
