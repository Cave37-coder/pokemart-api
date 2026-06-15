"""
fix_all_eras.py
Fixes ALL wrong era assignments based on Bulbapedia source of truth.
Run with DATABASE_URL uncommented in .env
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import CardSet, Era

# Create missing eras if they don't exist
needed_eras = [
    ('WotCN', 'WotC Neo Era'),
    ('WotCL', 'WotC Legendary Era'),
    ('WotCO', 'WotC e-Card Era'),
    ('HGSS',  'HeartGold SoulSilver Era'),
    ('MEG',   'Mega Evolution Era'),
]
for code, name in needed_eras:
    era, created = Era.objects.get_or_create(code=code, defaults={'name': name})
    if created:
        print(f"Created era: {code} ({name})")

# Map: set_code -> correct_era_code
CORRECT_ERAS = {
    # ── WotC Neo (N1-N4) ──
    'N1': 'WotCN', 'N2': 'WotCN', 'N3': 'WotCN', 'N4': 'WotCN',
    # ── WotC Legendary Collection ──
    'LC': 'WotCL',
    # ── WotC e-Card (Expedition, Aquapolis, Skyridge) ──
    'EX': 'WotCO', 'EXP': 'WotCO', 'AQ': 'WotCO', 'SK': 'WotCO',
    # ── WotC Original (ensure correct) ──
    'BS': 'WotC', 'JU': 'WotC', 'FO': 'WotC', 'B2': 'WotC',
    'TR': 'WotC', 'G1': 'WotC', 'G2': 'WotC', 'BSS': 'WotC',
    'SI1': 'WotC', 'PR-WB': 'WotC', 'PR-NB': 'WotC', 'BS2': 'WotC',
    # ── HGSS (HS, UL, UD, TM, CL — currently under DP) ──
    'HS': 'HGSS', 'UL': 'HGSS', 'UD': 'HGSS', 'TM': 'HGSS', 'CL': 'HGSS',
    'PR-HS': 'HGSS', 'TK-HS': 'HGSS', 'CoL': 'HGSS',
    # ── MEG (already fixed but ensure) ──
    'MEG': 'MEG', 'PFL': 'MEG', 'ASC': 'MEG', 'POR': 'MEG',
    'CRI': 'MEG', 'PBL': 'MEG', 'MEE': 'MEG', 'MEP': 'MEG', '30C': 'MEG',
}

fixed = 0
not_found = []

for set_code, era_code in CORRECT_ERAS.items():
    try:
        era = Era.objects.get(code=era_code)
        updated = CardSet.objects.filter(code=set_code).exclude(era=era).update(era=era)
        if updated:
            print(f"FIXED: {set_code} -> {era_code}")
            fixed += 1
    except Era.DoesNotExist:
        not_found.append(f"Era {era_code} not found for {set_code}")

print(f"\nFixed: {fixed} sets")
if not_found:
    print("Errors:")
    for e in not_found:
        print(f"  {e}")

print("\nDone. Run dump_sets.py to verify.")
