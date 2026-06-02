from products.models import Era, CardSet

# Fix the remaining unmapped sets
SET_ERA_MAP2 = {
    # WotC Base
    'B2': ('WotC', 'WotC Era'),
    'G1': ('WotC', 'WotC Era'),
    'G2': ('WotC', 'WotC Era'),
    'PR-WB': ('WotC', 'WotC Era'),
    'PR-NP': ('WotC', 'WotC Era'),
    'BP': ('WotC', 'WotC Era'),
    'RU1': ('WotC', 'WotC Era'),
    # EX Era
    'TK1A': ('EX', 'EX Era'),
    'TK1B': ('EX', 'EX Era'),
    'TK2A': ('EX', 'EX Era'),
    'TK2B': ('EX', 'EX Era'),
    'TRR': ('EX', 'EX Era'),
    'DX': ('EX', 'EX Era'),
    'EM': ('EX', 'EX Era'),
    'UF': ('EX', 'EX Era'),
    'PR-DPP': ('DP', 'Diamond & Pearl Era'),
    # XY
    'KSS': ('XY', 'XY Era'),
    # SM
    'SM03': ('SM', 'Sun & Moon Era'),
    'SM04': ('SM', 'Sun & Moon Era'),
    'SM05': ('SM', 'Sun & Moon Era'),
    'SHL': ('SM', 'Sun & Moon Era'),
    # SWSH
    'CPA': ('SWSH', 'Sword & Shield Era'),
    'BRSTG': ('SWSH', 'Sword & Shield Era'),
    'SITTG': ('SWSH', 'Sword & Shield Era'),
    'SHFSV': ('SWSH', 'Sword & Shield Era'),
    # SV
    'TOT24': ('TOT', 'Trick or Trade'),
    'PPS6': ('PRIZE', 'Prize Pack Series'),
    'PPS7': ('PRIZE', 'Prize Pack Series'),
    'PPS8': ('PRIZE', 'Prize Pack Series'),
    'ME05': ('MEG', 'Mega Evolution Era'),
}

# Get era cache
era_cache = {}
for code, (era_code, era_name) in SET_ERA_MAP2.items():
    if era_code not in era_cache:
        era_obj, _ = Era.objects.get_or_create(code=era_code, defaults={'name': era_name})
        era_cache[era_code] = era_obj

updated = 0
for set_code, (era_code, era_name) in SET_ERA_MAP2.items():
    try:
        cs = CardSet.objects.get(code=set_code)
        cs.era = era_cache[era_code]
        cs.save(update_fields=['era'])
        updated += 1
        print(f"  Fixed [{set_code}] -> {era_code}")
    except CardSet.DoesNotExist:
        print(f"  Not in DB: {set_code}")

print(f"\nUpdated {updated} sets")

# Show remaining unmapped
remaining = CardSet.objects.select_related('era').exclude(
    era__code__in=['WotC','WotCL','WotCN','WotCO','EX','DP','HGSS','BW','XY','SM','SWSH','SV','MEG','PRIZE','TOT','PROMO']
)
print(f"\nStill unmapped: {remaining.count()}")
for s in remaining[:20]:
    print(f"  [{s.code}] {s.name} -> era: {s.era.code if s.era else 'None'}")
