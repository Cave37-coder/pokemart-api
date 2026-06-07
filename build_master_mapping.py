"""
build_master_mapping.py
Produces a complete mapping of every set across all three sources:
  1. Our Railway DB (set codes, names, eras, record counts)
  2. TCGCSV (group IDs)
  3. pokemontcg.io (set IDs, card counts)

Output: master_set_mapping.csv
Run: python build_master_mapping.py
"""
import os, django, requests, csv
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Count
from products.models import PokemonProduct, CardSet

TCGCSV_GROUPS = {
    "BS":604,"BS2":605,"FO":630,"JU":635,"SI1":648,"TR":1373,
    "G1":1441,"G2":1440,"N1":1396,"N2":1434,"N3":1389,"N4":1444,
    "LC":1374,"BSS":1663,"PR-WB":1418,"PR-BEST":1455,
    "EX":1375,"AQ":1397,"SK":1372,"RS":1393,"SS":1392,"DR":1376,
    "MA":1377,"HL":1416,"RG":1419,"TRR":1428,"DS":1429,"EM":1410,
    "UF":1398,"DF":1411,"CG":1395,"HP":1379,"LM":1378,"PK":1383,
    "DP":1430,"MT":1368,"SW":1380,"GE":1405,"MD":1390,"LA":1417,
    "SF":1369,"PL":1406,"RR":1367,"SV":1384,"AR":1391,
    "HS":1402,"UL":1399,"UD":1403,"TM":1381,"CL":1415,"CoL":1415,
    "BLW":1400,"EPO":1424,"NVI":1385,"NXD":1412,"DEX":1386,
    "DRX":1394,"DRV":1426,"BCR":1408,"PLS":1413,"PLF":1382,
    "PLB":1370,"LTR":1409,"LTRRC":1465,
    "KSS":1522,"XY":1387,"FLF":1464,"FFI":1481,"PHF":1494,
    "PRC":1509,"DCR":1525,"ROS":1534,"AOR":1576,"BKT":1661,
    "BKP":1701,"GEN":1728,"GENRC":1729,"FCO":1780,"STS":1815,"EVO":1842,
    "SUM":1863,"GRI":1919,"BUS":1957,"SLG":2054,"CIN":2071,
    "UPR":2178,"FLI":2209,"CES":2278,"DRM":2295,"LOT":2328,
    "TEU":2377,"DET":2409,"UNB":2420,"UNM":2464,"HIF":2480,
    "HIFSV":2594,"CEC":2534,
    "SWSH01":2585,"SWSH02":2626,"SWSH03":2675,"CPA":2685,
    "SWSH04":2701,"SHF":2754,"SHFSV":2781,"SWSH05":2765,
    "MCD21":2782,"SWSH06":2807,"SWSH07":2848,"CLB":2867,
    "CCC":2931,"SWSH08":2906,"SWSH09":2948,"BRSTG":3020,
    "SWSH10":3040,"PGO":3064,"ASRTG":3068,"SWSH11":3118,
    "LORTG":3172,"SWSH12":3170,"SITTG":17674,"CRZ":17688,"CRZGG":17689,
    "TOT22":3179,"MCD22":3150,
    "SVI":22873,"PRIZEPACK":22880,"PAL":23120,"OBF":23228,
    "MEW":23237,"TOT23":23266,"PAR":23286,"MCD23":23306,
    "TCGCL":23323,"PAF":23353,"TEF":23381,"TWM":23473,
    "SFA":23529,"SCR":23537,"TOT24":23561,"SSP":23651,
    "PRE":23821,"JTG":24073,"MCD24":24163,"DRI":24269,
    "BLK":24325,"WHT":24326,"SVE":24382,
    "MEG":24380,"PFL":24448,"MEP":24451,"MEE":24461,
    "ASC":24541,"POR":24587,"CRI":24655,
}

PTCGIO_MAP = {
    "BS":"base1","BS2":"base4","BSS":"basep","FO":"base3","JU":"base2",
    "TR":"base5","G1":"gym1","G2":"gym2","SI1":"si1",
    "N1":"neo1","N2":"neo2","N3":"neo3","N4":"neo4","LC":"base6",
    "EX":"ecard1","AQ":"ecard2","SK":"ecard3",
    "RS":"ex1","SS":"ex2","DR":"ex3","MA":"ex4","HL":"ex5","RG":"ex6",
    "TRR":"ex7","EM":"ex9","UF":"ex10","DS":"ex11","LM":"ex12",
    "HP":"ex13","CG":"ex14","DF":"ex15","PK":"ex16",
    "DP":"dp1","MT":"dp2","SW":"dp3","GE":"dp4","MD":"dp5","LA":"dp6",
    "SF":"dp7","PL":"pl1","RR":"pl2","SV":"pl3","AR":"pl4",
    "HS":"hgss1","UL":"hgss2","UD":"hgss3","TM":"hgss4",
    "CL":"col1","CoL":"col1",
    "BLW":"bw1","EPO":"bw2","NVI":"bw3","NXD":"bw4","DEX":"bw5",
    "DRX":"bw6","DRV":"dv1","BCR":"bw7","PLS":"bw8","PLF":"bw9",
    "PLB":"bw10","LTR":"bw11","LTRRC":"bw11",
    "KSS":"xy0","XY":"xy1","FLF":"xy2","FFI":"xy3","PHF":"xy4",
    "PRC":"xy5","DCR":"dc1","ROS":"xy6","AOR":"xy7","BKT":"xy8",
    "BKP":"xy9","GEN":"g1","GENRC":"g1","FCO":"xy10","STS":"xy11","EVO":"xy12",
    "SUM":"sm1","GRI":"sm2","BUS":"sm3","SLG":"sm35","CIN":"sm4",
    "UPR":"sm5","FLI":"sm6","CES":"sm7","DRM":"sm75","LOT":"sm8",
    "TEU":"sm9","DET":"det1","UNB":"sm10","UNM":"sm11",
    "HIF":"sm115","HIFSV":"sma","CEC":"sm12",
    "SWSH01":"swsh1","SWSH02":"swsh2","SWSH03":"swsh3","CPA":"swsh35",
    "SWSH04":"swsh4","SHF":"swsh45","SHFSV":"swsh45sv","SWSH05":"swsh5",
    "SWSH06":"swsh6","SWSH07":"swsh7","CLB":"cel25","CCC":"cel25c",
    "SWSH08":"swsh8","SWSH09":"swsh9","BRSTG":"swsh9tg","BST":"swsh9tg",
    "SWSH10":"swsh10","ASRTG":"swsh10tg","PGO":"pgo",
    "SWSH11":"swsh11","LORTG":"swsh11tg",
    "SWSH12":"swsh12","SITTG":"swsh12tg","ST":"swsh12tg",
    "CRZ":"swsh12pt5","CRZGG":"swsh12pt5gg",
    "SVI":"sv1","PAL":"sv2","OBF":"sv3","MEW":"sv3pt5","PAR":"sv4",
    "PAF":"sv4pt5","TEF":"sv5","TWM":"sv6","SFA":"sv6pt5","SCR":"sv7",
    "SSP":"sv8","PRE":"sv8pt5","JTG":"sv9","DRI":"sv10",
    # MEG era - not yet on pokemontcg.io
    "MEG":None,"PFL":None,"ASC":None,"POR":None,"CRI":None,"PBL":None,
    "MEE":None,"MEP":None,
}

# Fetch all sets from pokemontcg.io
print("Fetching all sets from pokemontcg.io...")
try:
    r = requests.get(
        "https://api.pokemontcg.io/v2/sets?pageSize=250&orderBy=releaseDate",
        timeout=60)
    ptcgio_sets = r.json().get("data", [])
    print(f"Got {len(ptcgio_sets)} sets from pokemontcg.io")
except Exception as e:
    print(f"pokemontcg.io fetch failed: {e}")
    ptcgio_sets = []

ptcgio_by_id = {s['id']: s for s in ptcgio_sets}

# Read DB sets with record counts
print("Reading DB sets and record counts...")
db_sets = list(CardSet.objects.select_related('era').order_by(
    'era__code', 'release_date', 'code'
).values('code', 'name', 'era__code', 'release_date'))

record_counts = {
    row['card_set__code']: row['count']
    for row in PokemonProduct.objects.values('card_set__code').annotate(count=Count('id'))
}

print(f"DB sets: {len(db_sets)}")

# Build rows
rows = []
for db in db_sets:
    code         = db['code']
    tcgcsv_gid   = TCGCSV_GROUPS.get(code, '')
    ptcgio_id    = PTCGIO_MAP.get(code, '')
    db_records   = record_counts.get(code, 0)
    ptcgio_info  = ptcgio_by_id.get(ptcgio_id or '', {})

    if ptcgio_id and ptcgio_id in ptcgio_by_id:
        ptcgio_status = 'CONFIRMED'
    elif ptcgio_id is None:
        ptcgio_status = 'NOT_YET'
    elif ptcgio_id == '':
        ptcgio_status = 'NO_MAPPING'
    else:
        ptcgio_status = 'ID_NOT_FOUND'

    rows.append({
        'db_code':         code,
        'db_name':         db['name'],
        'era':             db['era__code'] or '',
        'release_date':    str(db['release_date']) if db['release_date'] else '',
        'db_records':      db_records,
        'tcgcsv_gid':      tcgcsv_gid or '',
        'ptcgio_id':       ptcgio_id or '',
        'ptcgio_name':     ptcgio_info.get('name', ''),
        'ptcgio_total':    ptcgio_info.get('total', ''),
        'ptcgio_status':   ptcgio_status,
        'enrich_source':   ('ptcgio' if ptcgio_status == 'CONFIRMED'
                            else 'tcgcsv' if tcgcsv_gid
                            else 'none'),
        'notes': '',
    })

# Write CSV
with open('master_set_mapping.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"\nWritten: master_set_mapping.csv")
print()

# Print full report
print("=" * 80)
print("MASTER SET MAPPING REPORT")
print("=" * 80)
print(f"{'ERA':<10} {'CODE':<12} {'RECORDS':<10} {'TCGCSV':<10} {'PTCGIO_ID':<16} {'PTCGIO_STATUS':<16} ENRICH_VIA")
print("-" * 90)

current_era = None
for row in rows:
    if row['era'] != current_era:
        current_era = row['era']
        print(f"\n  -- {current_era} ----------")
    print(
        f"  {row['era']:<10} {row['db_code']:<12} {row['db_records']:<10} "
        f"{str(row['tcgcsv_gid']):<10} {str(row['ptcgio_id']):<16} "
        f"{row['ptcgio_status']:<16} {row['enrich_source']}"
    )

print()
print("=" * 80)
print("TOTALS:")
print(f"  Total sets in DB:           {len(rows)}")
print(f"  Sets with DB records:       {sum(1 for r in rows if r['db_records'] > 0)}")
print(f"  Enrich via ptcgio:          {sum(1 for r in rows if r['enrich_source'] == 'ptcgio')}")
print(f"  Enrich via tcgcsv only:     {sum(1 for r in rows if r['enrich_source'] == 'tcgcsv')}")
print(f"  No enrichment source:       {sum(1 for r in rows if r['enrich_source'] == 'none')}")
print(f"  ptcgio CONFIRMED:           {sum(1 for r in rows if r['ptcgio_status'] == 'CONFIRMED')}")
print(f"  ptcgio NOT_YET (MEG era):   {sum(1 for r in rows if r['ptcgio_status'] == 'NOT_YET')}")
print(f"  ptcgio NO_MAPPING:          {sum(1 for r in rows if r['ptcgio_status'] == 'NO_MAPPING')}")