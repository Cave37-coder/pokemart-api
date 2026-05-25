from products.models import CardSet
from datetime import date

# Complete correct release dates from Bulbapedia reference
# Format: 'CODE': date(YYYY, MM, DD)
CORRECT_DATES = {
    # Scarlet & Violet
    'SVI':  date(2023, 3, 31),
    'PAL':  date(2023, 6, 9),
    'OBF':  date(2023, 8, 11),
    'MEW':  date(2023, 9, 22),
    'PAR':  date(2023, 11, 3),
    'PAF':  date(2024, 1, 26),
    'TEF':  date(2024, 3, 22),
    'TWM':  date(2024, 5, 24),
    'SFA':  date(2024, 8, 2),
    'SCR':  date(2024, 9, 13),
    'SSP':  date(2024, 11, 8),
    'PRE':  date(2025, 1, 17),
    'JTG':  date(2025, 3, 28),
    'DRI':  date(2025, 5, 30),
    'BLK':  date(2025, 7, 18),
    # Mega Evolution
    'MEG':  date(2025, 9, 26),
    'PFL':  date(2025, 11, 14),
    'ASC':  date(2026, 1, 30),
    'POR':  date(2026, 3, 27),
    'CRI':  date(2026, 5, 22),
    'PBL':  date(2026, 7, 17),
    # Promos / Energies
    'MEP':  date(2025, 9, 26),
    'MEE':  date(2025, 9, 26),
    # Sword & Shield
    'SSH':  date(2020, 2, 7),
    'RCL':  date(2020, 5, 1),
    'DAA':  date(2020, 8, 14),
    'CPA':  date(2020, 9, 25),
    'VIV':  date(2020, 11, 13),
    'SHF':  date(2021, 2, 19),
    'BST':  date(2021, 3, 19),
    'CRE':  date(2021, 6, 18),
    'EVS':  date(2021, 8, 27),
    'CEL':  date(2021, 10, 8),
    'FST':  date(2021, 11, 12),
    'BRS':  date(2022, 2, 25),
    'ASR':  date(2022, 5, 27),
    'PGO':  date(2022, 7, 1),
    'LOR':  date(2022, 9, 9),
    'SIT':  date(2022, 11, 11),
    'CRZ':  date(2023, 1, 20),
    # Trick or Trade
    'TT22': date(2022, 9, 1),
    'TT23': date(2023, 9, 1),
    'TT24': date(2024, 8, 30),
    # McDonalds
    'MCD24': date(2024, 12, 4),
    'MCD23': date(2023, 7, 27),
    'MCD22': date(2022, 8, 3),
    # Play Prize Packs
    'PPS1': date(2022, 11, 9),
    'PPS2': date(2023, 1, 19),
    'PPS3': date(2023, 8, 14),
    'PPS4': date(2024, 2, 14),
    'PPS5': date(2024, 8, 14),
    'PPS6': date(2025, 2, 14),
    'PPS7': date(2025, 8, 14),
    'PPS8': date(2026, 1, 1),
    # SVP / SVE
    'SVP':  date(2023, 1, 1),
    'SVE':  date(2023, 3, 31),
}

updated = 0
not_found = []
for code, correct_date in CORRECT_DATES.items():
    count = CardSet.objects.filter(code=code).update(release_date=correct_date)
    if count:
        updated += 1
    else:
        not_found.append(code)

print(f"Updated: {updated} sets")
print(f"Not in DB (skipped): {not_found}")

# Show current state of Mega Evolution sets to verify
print("\nMega Evolution sets after fix:")
for s in CardSet.objects.filter(code__in=['MEG','PFL','ASC','POR','CRI','PBL','BLK','WHT','DRI']).order_by('-release_date'):
    print(f"  {s.code:<8} {s.release_date}  {s.name}")
