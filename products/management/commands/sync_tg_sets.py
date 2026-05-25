"""
Sync Trainer Gallery, Shiny Vault and Radiant Collection sets
These have prefixed card numbers (TG01, SV1, GG19, RC1) that were skipped before
Run: python manage.py shell --command="exec(open('sync_tg_sets.py').read())"
"""
import subprocess
import sys

TG_SETS = ['ASRTG', 'LORTG', 'ST', 'CRZGG', 'HIFSV', 'SHFSV', 'GENRC', 'LTRRC']

print(f"Syncing {len(TG_SETS)} sets with prefixed card numbers...")

for code in TG_SETS:
    print(f"\nSyncing {code}...", flush=True)
    result = subprocess.run(
        [sys.executable, 'manage.py', 'sync_tcgcsv', '--set-code', code],
        capture_output=True, text=True
    )
    lines = (result.stdout + result.stderr).strip().split('\n')
    for line in lines[-4:]:
        if line.strip():
            print(f"  {line}")

print("\nAll done!")
