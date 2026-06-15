"""
Fix era codes and names directly in the DB.
Run: python manage.py shell < fix_eras.py
Or: python manage.py runscript fix_eras  (if django-extensions installed)
"""

from products.models import Era, CardSet

# Map wrong era codes -> correct (code, name)
# These are the garbage codes created by the bad get_era_code() fallback
ERA_FIXES = {
    # The bad codes were created by taking era_name[:10].replace(' ','')
    # We need to find them by their current wrong code and fix them
}

# Better approach: fix by CardSet code since we know exactly which set belongs to which era
SET_ERA_MAP = {
    # WotC Base
    'BS': ('WotC', 'WotC Era'),
    'BS2': ('WotC', 'WotC Era'),
    'JU': ('WotC', 'WotC Era'),
    'FO': ('WotC', 'WotC Era'),
    'TR': ('WotC', 'WotC Era'),
    'SI1': ('WotC', 'WotC Era'),
    # WotC Legendary
    'LC': ('WotCL', 'WotC Legendary Era'),
    'SK': ('WotCL', 'WotC Legendary Era'),
    # WotC Neo
    'N1': ('WotCN', 'WotC Neo Era'),
    'N2': ('WotCN', 'WotC Neo Era'),
    'N3': ('WotCN', 'WotC Neo Era'),
    'N4': ('WotCN', 'WotC Neo Era'),
    # WotC Other
    'EX': ('WotCO', 'WotC Other'),
    'AQ': ('WotCO', 'WotC Other'),
    'RR': ('WotCO', 'WotC Other'),
    # EX Era
    'RS': ('EX', 'EX Era'),
    'SS': ('EX', 'EX Era'),
    'DR': ('EX', 'EX Era'),
    'MA': ('EX', 'EX Era'),
    'HL': ('EX', 'EX Era'),
    'RG': ('EX', 'EX Era'),
    'SK2': ('EX', 'EX Era'),
    'EX7': ('EX', 'EX Era'),
    'DS': ('EX', 'EX Era'),
    'LM': ('EX', 'EX Era'),
    'HP': ('EX', 'EX Era'),
    'CG': ('EX', 'EX Era'),
    'DF': ('EX', 'EX Era'),
    'PK': ('EX', 'EX Era'),
    'MT': ('EX', 'EX Era'),
    'SW': ('EX', 'EX Era'),
    'GE': ('EX', 'EX Era'),
    'MD': ('EX', 'EX Era'),
    'LA': ('EX', 'EX Era'),
    'SF': ('EX', 'EX Era'),
    # DP Era
    'DP': ('DP', 'Diamond & Pearl Era'),
    'MT2': ('DP', 'Diamond & Pearl Era'),
    'SW2': ('DP', 'Diamond & Pearl Era'),
    'GE2': ('DP', 'Diamond & Pearl Era'),
    'MD2': ('DP', 'Diamond & Pearl Era'),
    'LA2': ('DP', 'Diamond & Pearl Era'),
    'SF2': ('DP', 'Diamond & Pearl Era'),
    'PLB': ('DP', 'Diamond & Pearl Era'),
    'RR2': ('DP', 'Diamond & Pearl Era'),
    'SV2': ('DP', 'Diamond & Pearl Era'),
    'AR': ('DP', 'Diamond & Pearl Era'),
    'TM': ('DP', 'Diamond & Pearl Era'),
    'UL': ('DP', 'Diamond & Pearl Era'),
    'UD': ('DP', 'Diamond & Pearl Era'),
    'TR2': ('DP', 'Diamond & Pearl Era'),
    'CL': ('DP', 'Diamond & Pearl Era'),
    # HGSS
    'HS': ('HGSS', 'HeartGold SoulSilver Era'),
    'COL': ('HGSS', 'HeartGold SoulSilver Era'),
    'HGSS': ('HGSS', 'HeartGold SoulSilver Era'),
    'CoL': ('HGSS', 'HeartGold SoulSilver Era'),
    # BW
    'BW': ('BW', 'Black & White Era'),
    'EPO': ('BW', 'Black & White Era'),
    'NVI': ('BW', 'Black & White Era'),
    'NXD': ('BW', 'Black & White Era'),
    'DEX': ('BW', 'Black & White Era'),
    'DRX': ('BW', 'Black & White Era'),
    'DRV': ('BW', 'Black & White Era'),
    'BCR': ('BW', 'Black & White Era'),
    'PLS': ('BW', 'Black & White Era'),
    'PLF': ('BW', 'Black & White Era'),
    'PLB': ('BW', 'Black & White Era'),
    'LTR': ('BW', 'Black & White Era'),
    'BWP': ('BW', 'Black & White Era'),
    # XY
    'XY': ('XY', 'XY Era'),
    'FLF': ('XY', 'XY Era'),
    'FFI': ('XY', 'XY Era'),
    'PHF': ('XY', 'XY Era'),
    'PRC': ('XY', 'XY Era'),
    'DCE': ('XY', 'XY Era'),
    'ROS': ('XY', 'XY Era'),
    'AOR': ('XY', 'XY Era'),
    'BKP': ('XY', 'XY Era'),
    'GEN': ('XY', 'XY Era'),
    'FCO': ('XY', 'XY Era'),
    'STS': ('XY', 'XY Era'),
    'EVO': ('XY', 'XY Era'),
    'XYP': ('XY', 'XY Era'),
    'BKT': ('XY', 'XY Era'),
    # SM
    'SUM': ('SM', 'Sun & Moon Era'),
    'GRI': ('SM', 'Sun & Moon Era'),
    'BUS': ('SM', 'Sun & Moon Era'),
    'SLG': ('SM', 'Sun & Moon Era'),
    'CIN': ('SM', 'Sun & Moon Era'),
    'UPR': ('SM', 'Sun & Moon Era'),
    'FLI': ('SM', 'Sun & Moon Era'),
    'CES': ('SM', 'Sun & Moon Era'),
    'DRM': ('SM', 'Sun & Moon Era'),
    'LOT': ('SM', 'Sun & Moon Era'),
    'TEU': ('SM', 'Sun & Moon Era'),
    'DET': ('SM', 'Sun & Moon Era'),
    'UNB': ('SM', 'Sun & Moon Era'),
    'UNM': ('SM', 'Sun & Moon Era'),
    'HIF': ('SM', 'Sun & Moon Era'),
    'CEC': ('SM', 'Sun & Moon Era'),
    'SMP': ('SM', 'Sun & Moon Era'),
    'SM01': ('SM', 'Sun & Moon Era'),
    'SM02': ('SM', 'Sun & Moon Era'),
    'SM8': ('SM', 'Sun & Moon Era'),
    'SM9': ('SM', 'Sun & Moon Era'),
    'SM10': ('SM', 'Sun & Moon Era'),
    'SM11': ('SM', 'Sun & Moon Era'),
    'SM12': ('SM', 'Sun & Moon Era'),
    # SWSH
    'SSH': ('SWSH', 'Sword & Shield Era'),
    'RCL': ('SWSH', 'Sword & Shield Era'),
    'DAA': ('SWSH', 'Sword & Shield Era'),
    'VIV': ('SWSH', 'Sword & Shield Era'),
    'SHF': ('SWSH', 'Sword & Shield Era'),
    'BST': ('SWSH', 'Sword & Shield Era'),
    'CRE': ('SWSH', 'Sword & Shield Era'),
    'EVS': ('SWSH', 'Sword & Shield Era'),
    'FST': ('SWSH', 'Sword & Shield Era'),
    'BRS': ('SWSH', 'Sword & Shield Era'),
    'ASR': ('SWSH', 'Sword & Shield Era'),
    'PGO': ('SWSH', 'Sword & Shield Era'),
    'LOR': ('SWSH', 'Sword & Shield Era'),
    'SIT': ('SWSH', 'Sword & Shield Era'),
    'CRZ': ('SWSH', 'Sword & Shield Era'),
    'CRZGG': ('SWSH', 'Sword & Shield Era'),
    'SWSH05': ('SWSH', 'Sword & Shield Era'),
    'CHP': ('SWSH', 'Sword & Shield Era'),
    'SWP': ('SWSH', 'Sword & Shield Era'),
    'PR-SW': ('SWSH', 'Sword & Shield Era'),
    # SV
    'SV1': ('SV', 'Scarlet & Violet Era'),
    'SV2': ('SV', 'Scarlet & Violet Era'),
    'SV3': ('SV', 'Scarlet & Violet Era'),
    'SV3PT5': ('SV', 'Scarlet & Violet Era'),
    'SV4': ('SV', 'Scarlet & Violet Era'),
    'SV4PT5': ('SV', 'Scarlet & Violet Era'),
    'SV5': ('SV', 'Scarlet & Violet Era'),
    'SV6': ('SV', 'Scarlet & Violet Era'),
    'SV6PT5': ('SV', 'Scarlet & Violet Era'),
    'SV7': ('SV', 'Scarlet & Violet Era'),
    'SV8': ('SV', 'Scarlet & Violet Era'),
    'SV8PT5': ('SV', 'Scarlet & Violet Era'),
    'SVP': ('SV', 'Scarlet & Violet Era'),
    'SVE': ('SV', 'Scarlet & Violet Era'),
    'MEW': ('SV', 'Scarlet & Violet Era'),
    'PAL': ('SV', 'Scarlet & Violet Era'),
    'OBF': ('SV', 'Scarlet & Violet Era'),
    'PAR': ('SV', 'Scarlet & Violet Era'),
    'PAF': ('SV', 'Scarlet & Violet Era'),
    'TEF': ('SV', 'Scarlet & Violet Era'),
    'TWM': ('SV', 'Scarlet & Violet Era'),
    'SVI': ('SV', 'Scarlet & Violet Era'),
    'SCR': ('SV', 'Scarlet & Violet Era'),
    'SSP': ('SV', 'Scarlet & Violet Era'),
    'PR-SV': ('SV', 'Scarlet & Violet Era'),
    'SV3PT5': ('SV', 'Scarlet & Violet Era'),
    'SV4PT5': ('SV', 'Scarlet & Violet Era'),
    'ITCG': ('SV', 'Scarlet & Violet Era'),
    'SITC': ('SV', 'Scarlet & Violet Era'),
    # Mega Evolution
    'MEG': ('MEG', 'Mega Evolution Era'),
    # Prize Pack
    'PPS1': ('PRIZE', 'Prize Pack Series'),
    'PPS2': ('PRIZE', 'Prize Pack Series'),
    'PPS3': ('PRIZE', 'Prize Pack Series'),
    'PPS4': ('PRIZE', 'Prize Pack Series'),
    'PPS5': ('PRIZE', 'Prize Pack Series'),
    # Trick or Trade
    'TK1': ('TOT', 'Trick or Trade'),
    'TK2': ('TOT', 'Trick or Trade'),
    'TK24': ('TOT', 'Trick or Trade'),
    'TOT23': ('TOT', 'Trick or Trade'),
    # McDonalds
    'MCD11': ('PROMO', 'Promo'),
    'MCD12': ('PROMO', 'Promo'),
    'MCD15': ('PROMO', 'Promo'),
    'MCD17': ('PROMO', 'Promo'),
    'MCD19': ('PROMO', 'Promo'),
    'MCD21': ('PROMO', 'Promo'),
    'MCD22': ('PROMO', 'Promo'),
    'MCD23': ('PROMO', 'Promo'),
}

print("Fixing eras...")

# Get or create all needed eras
era_cache = {}
for set_code, (era_code, era_name) in SET_ERA_MAP.items():
    if era_code not in era_cache:
        era_obj, created = Era.objects.get_or_create(code=era_code, defaults={'name': era_name})
        era_cache[era_code] = era_obj
        if created:
            print(f"  Created era: {era_code} - {era_name}")

# Update each CardSet
updated = 0
not_found = []
for set_code, (era_code, era_name) in SET_ERA_MAP.items():
    try:
        cs = CardSet.objects.get(code=set_code)
        era_obj = era_cache[era_code]
        if cs.era != era_obj:
            cs.era = era_obj
            cs.save(update_fields=['era'])
            updated += 1
    except CardSet.DoesNotExist:
        not_found.append(set_code)

print(f"Updated {updated} CardSets")
if not_found:
    print(f"Not found in DB: {not_found}")

# Now fix any remaining sets that have wrong era codes (the B1-B9 garbage)
# by checking all sets not in our map
all_sets = CardSet.objects.select_related('era').all()
unmapped = [(s.code, s.era.code if s.era else 'None', s.name) for s in all_sets if s.code not in SET_ERA_MAP]
if unmapped:
    print(f"\nUnmapped sets still in DB ({len(unmapped)}):")
    for code, era, name in unmapped[:30]:
        print(f"  [{code}] {name} -> era: {era}")

print("\nDone!")
