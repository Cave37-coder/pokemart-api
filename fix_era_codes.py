"""
fix_era_codes.py
Fixes wrong era assignments in Railway DB based on Bulbapedia source of truth.
Run with DATABASE_URL uncommented in .env
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import CardSet, Era

fixes = [
    # (set_code, correct_era_code, reason)
    ('RR',  'DP',  'Rising Rivals = Platinum Series = DP era, not WotCO'),
    ('DCR', 'XY',  'Double Crisis = XY Series Special, not BW'),
    ('ASC', 'MEG', 'Ascended Heroes = Mega Evolution ME2.5, not SV'),
    ('PFL', 'MEG', 'Phantasmal Flames = Mega Evolution ME2, not SV'),
    ('POR', 'MEG', 'Perfect Order = Mega Evolution ME3, not SV'),
    ('CRI', 'MEG', 'Chaos Rising = Mega Evolution ME4, not SV'),
    ('MEE', 'MEG', 'Mega Evolution Energies = MEG era'),
    ('MEP', 'MEG', 'Mega Evolution Promos = MEG era'),
]

for set_code, era_code, reason in fixes:
    try:
        era = Era.objects.get(code=era_code)
        updated = CardSet.objects.filter(code=set_code).update(era=era)
        if updated:
            print(f"FIXED: {set_code} -> {era_code} ({reason})")
        else:
            print(f"NOT FOUND: {set_code} (set doesn't exist in DB)")
    except Era.DoesNotExist:
        print(f"ERA NOT FOUND: {era_code} for {set_code}")

# Also fix PBL/ME05 code
try:
    s = CardSet.objects.filter(code='ME05').first()
    if s:
        s.code = 'PBL'
        s.save()
        print("FIXED: ME05 -> PBL (Pitch Black correct code)")
    else:
        print("ME05 not found (may already be PBL)")
except Exception as e:
    print(f"PBL fix error: {e}")

print("\nDone. Verify by running dump_sets.py again.")
