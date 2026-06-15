from products.models import Era, CardSet

SET_ERA_MAP3 = {
    # WotC
    'BSS': ('WotC', 'WotC Era'),
    'PR-BEST': ('WotC', 'WotC Era'),
    'POP1': ('WotC', 'WotC Era'),
    'POP2': ('EX', 'EX Era'),
    'POP3': ('EX', 'EX Era'),
    'POP4': ('EX', 'EX Era'),
    'POP5': ('EX', 'EX Era'),
    'POP6': ('DP', 'Diamond & Pearl Era'),
    'POP7': ('DP', 'Diamond & Pearl Era'),
    'POP8': ('DP', 'Diamond & Pearl Era'),
    'POP9': ('DP', 'Diamond & Pearl Era'),
    # DP/Platinum
    'PL': ('DP', 'Diamond & Pearl Era'),
    'SV': ('DP', 'Diamond & Pearl Era'),
    'RUM': ('DP', 'Diamond & Pearl Era'),
    'PR-HS': ('HGSS', 'HeartGold SoulSilver Era'),
    'LTRRC': ('BW', 'Black & White Era'),
    # BW
    'BLW': ('BW', 'Black & White Era'),
    'PR-BLW': ('BW', 'Black & White Era'),
    'DCR': ('BW', 'Black & White Era'),
    # XY
    'MCD14': ('XY', 'XY Era'),
    'MCD16': ('XY', 'XY Era'),
    'GENRC': ('XY', 'XY Era'),
    'PR-XY': ('XY', 'XY Era'),
    'KSS': ('XY', 'XY Era'),
    # SM
    'MCD18': ('SM', 'Sun & Moon Era'),
    'PR-SM': ('SM', 'Sun & Moon Era'),
    'HIFSV': ('SM', 'Sun & Moon Era'),
    # SWSH
    'SWSH01': ('SWSH', 'Sword & Shield Era'),
    'SWSH02': ('SWSH', 'Sword & Shield Era'),
    'SWSH03': ('SWSH', 'Sword & Shield Era'),
    'SWSH04': ('SWSH', 'Sword & Shield Era'),
    'SWSH06': ('SWSH', 'Sword & Shield Era'),
    'SWSH07': ('SWSH', 'Sword & Shield Era'),
    'SWSH08': ('SWSH', 'Sword & Shield Era'),
    'SWSH09': ('SWSH', 'Sword & Shield Era'),
    'SWSH10': ('SWSH', 'Sword & Shield Era'),
    'SWSH11': ('SWSH', 'Sword & Shield Era'),
    'SWSH12': ('SWSH', 'Sword & Shield Era'),
    'ASRTG': ('SWSH', 'Sword & Shield Era'),
    'LORTG': ('SWSH', 'Sword & Shield Era'),
    'ST': ('SWSH', 'Sword & Shield Era'),
    'CLB': ('SWSH', 'Sword & Shield Era'),
    'CCC': ('SWSH', 'Sword & Shield Era'),
    'PR-SWSH': ('SWSH', 'Sword & Shield Era'),
    'MCD21': ('SWSH', 'Sword & Shield Era'),
    'MCD22': ('SWSH', 'Sword & Shield Era'),
    'TOT22': ('TOT', 'Trick or Trade'),
    'PRIZEPACK': ('PRIZE', 'Prize Pack Series'),
    # SV
    'PRE': ('SV', 'Scarlet & Violet Era'),
    'SFA': ('SV', 'Scarlet & Violet Era'),
    'TCGCL': ('SV', 'Scarlet & Violet Era'),
    'MCD24': ('SV', 'Scarlet & Violet Era'),
    'PR-SV': ('SV', 'Scarlet & Violet Era'),
    'JTG': ('SV', 'Scarlet & Violet Era'),
    'DRI': ('SV', 'Scarlet & Violet Era'),
    'BLK': ('SV', 'Scarlet & Violet Era'),
    'WHT': ('SV', 'Scarlet & Violet Era'),
    'PFL': ('SV', 'Scarlet & Violet Era'),
    'ASC': ('SV', 'Scarlet & Violet Era'),
    'CRI': ('SV', 'Scarlet & Violet Era'),
    'POR': ('SV', 'Scarlet & Violet Era'),
    # Mega Evolution
    'MEE': ('MEG', 'Mega Evolution Era'),
    'MEP': ('MEG', 'Mega Evolution Era'),
}

era_cache = {}
for code, (era_code, era_name) in SET_ERA_MAP3.items():
    if era_code not in era_cache:
        era_obj, _ = Era.objects.get_or_create(code=era_code, defaults={'name': era_name})
        era_cache[era_code] = era_obj

updated = 0
for set_code, (era_code, _) in SET_ERA_MAP3.items():
    try:
        cs = CardSet.objects.get(code=set_code)
        cs.era = era_cache[era_code]
        cs.save(update_fields=['era'])
        updated += 1
        print(f"  Fixed [{set_code}] -> {era_code}")
    except CardSet.DoesNotExist:
        print(f"  Not in DB: {set_code}")

print(f"\nUpdated {updated} sets")

good = ['WotC','WotCL','WotCN','WotCO','EX','DP','HGSS','BW','XY','SM','SWSH','SV','MEG','PRIZE','TOT','PROMO']
remaining = CardSet.objects.select_related('era').exclude(era__code__in=good)
print(f"Still unmapped: {remaining.count()}")
for s in remaining.order_by('code'):
    print(f"  [{s.code}] {s.name} -> {s.era.code if s.era else None}")
