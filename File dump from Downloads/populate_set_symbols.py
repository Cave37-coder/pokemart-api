"""
Populate symbol_url and logo_url for all CardSets using pokemontcg.io URL pattern
Run: python manage.py shell --command="exec(open('populate_set_symbols.py').read())"
"""
from products.models import CardSet

# Same SET_ID_MAP from enrich_only.py
SET_ID_MAP = {
    'BS': 'base1', 'BS2': 'base4', 'BSS': 'basep', 'FO': 'base3',
    'JU': 'base2', 'TR': 'base5', 'G1': 'gym1', 'G2': 'gym2',
    'N1': 'neo1', 'N2': 'neo2', 'N3': 'neo3', 'N4': 'neo4',
    'LC': 'base6', 'SI1': 'si1', 'PR-WB': 'basep', 'PR-BEST': 'basep',
    'EX': 'ecard1', 'AQ': 'ecard2', 'SK': 'ecard3',
    'RS': 'ex1', 'SS': 'ex2', 'DR': 'ex3', 'MA': 'ex4',
    'HL': 'ex5', 'RG': 'ex6', 'TRR': 'ex7', 'DX': 'ex8',
    'EM': 'ex9', 'UF': 'ex10', 'DS': 'ex11', 'LM': 'ex12',
    'HP': 'ex13', 'CG': 'ex14', 'DF': 'ex15', 'PK': 'ex16',
    'DP': 'dp1', 'MT': 'dp2', 'SW': 'dp3', 'GE': 'dp4',
    'MD': 'dp5', 'LA': 'dp6', 'SF': 'dp7', 'PL': 'pl1',
    'RR': 'pl2', 'SV': 'pl3', 'AR': 'pl4', 'HS': 'hgss1',
    'UL': 'hgss2', 'UD': 'hgss3', 'TM': 'hgss4', 'CoL': 'col1',
    'PR-HS': 'hsp', 'PR-DP': 'dpp', 'RUM': 'ru1',
    'BLW': 'bw1', 'EPO': 'bw2', 'NVI': 'bw3', 'NXD': 'bw4',
    'DEX': 'bw5', 'DRX': 'bw6', 'DRV': 'dv1', 'BCR': 'bw7',
    'PLS': 'bw8', 'PLF': 'bw9', 'PLB': 'bw10', 'LTR': 'bw11',
    'LTRRC': 'bw11', 'PR-BLW': 'bwp',
    'MCD11': 'mcd11', 'MCD12': 'mcd12', 'MCD14': 'mcd14',
    'MCD15': 'mcd15', 'MCD16': 'mcd16', 'MCD17': 'mcd17',
    'MCD18': 'mcd18', 'MCD19': 'mcd19',
    'KSS': 'xy0', 'XY': 'xy1', 'FLF': 'xy2', 'FFI': 'xy3',
    'PHF': 'xy4', 'PRC': 'xy5', 'DCR': 'dc1', 'ROS': 'xy6',
    'AOR': 'xy7', 'BKT': 'xy8', 'BKP': 'xy9', 'GEN': 'g1',
    'GENRC': 'g1', 'FCO': 'xy10', 'STS': 'xy11', 'EVO': 'xy12',
    'PR-XY': 'xyp',
    'SM01': 'sm1', 'SM02': 'sm2', 'SM03': 'sm3', 'SHL': 'sm35',
    'SM04': 'sm4', 'SM05': 'sm5', 'SM06': 'sm6', 'CES': 'sm7',
    'DRM': 'sm75', 'SM8': 'sm8', 'SM9': 'sm9', 'DEP': 'det1',
    'SM10': 'sm10', 'SM11': 'sm11', 'HIF': 'sm115',
    'HIFSV': 'sma', 'SM12': 'sm12', 'PR-SM': 'smp',
    'MCD21': 'mcd21',
    'SWSH01': 'swsh1', 'SWSH02': 'swsh2', 'SWSH03': 'swsh3',
    'CHP': 'swsh35', 'SWSH04': 'swsh4', 'SHF': 'swsh45',
    'SHFSV': 'swsh45sv', 'SWSH05': 'swsh5', 'SWSH06': 'swsh6',
    'SWSH07': 'swsh7', 'CLB': 'cel25', 'CCC': 'cel25c',
    'SWSH08': 'swsh8', 'SWSH09': 'swsh9', 'BST': 'swsh9tg',
    'SWSH10': 'swsh10', 'PGO': 'pgo', 'ASRTG': 'swsh10tg',
    'SWSH11': 'swsh11', 'LORTG': 'swsh11tg', 'SWSH12': 'swsh12',
    'ST': 'swsh12tg', 'CRZ': 'swsh12pt5', 'CRZGG': 'swsh12pt5gg',
    'TOT22': 'poptb', 'MCD22': 'mcd22', 'PR-SWSH': 'swshp',
    'SVP': 'svp', 'SVI': 'sv1', 'PRIZEPACK': 'svp',
    'PAL': 'sv2', 'OBF': 'sv3', 'MEW': 'sv3pt5',
    'TOT23': 'poptb', 'PAR': 'sv4', 'MCD23': 'mcd23',
    'TCGCL': 'mcd23', 'PAF': 'sv4pt5', 'TEF': 'sv5',
    'TWM': 'sv6', 'SFA': 'sv6pt5', 'SCR': 'sv7',
    'TOT24': 'poptb', 'SSP': 'sv8', 'PRE': 'sv8pt5',
    'JTG': 'sv9', 'MCD24': 'mcd24', 'DRI': 'sv10',
    'BLK': 'sv10pt5', 'WHT': 'sv10pt5', 'SVE': 'sve',
    'MEG': 'me1', 'PFL': 'me2', 'MEP': 'mep', 'MEE': 'mee',
    'ASC': 'me2pt5', 'POR': 'me3', 'CRI': 'me4',
    # POP Series
    'POP1': 'pop1', 'POP2': 'pop2', 'POP3': 'pop3', 'POP4': 'pop4',
    'POP5': 'pop5', 'POP6': 'pop6', 'POP7': 'pop7', 'POP8': 'pop8',
    'POP9': 'pop9',
}

BASE_URL = "https://images.pokemontcg.io"

updated = 0
skipped = 0
not_mapped = []

all_sets = CardSet.objects.all()
to_update = []

for cs in all_sets:
    ptcgio_id = SET_ID_MAP.get(cs.code)
    if not ptcgio_id:
        not_mapped.append(cs.code)
        continue

    symbol_url = f"{BASE_URL}/{ptcgio_id}/symbol.png"
    logo_url = f"{BASE_URL}/{ptcgio_id}/logo.png"

    if cs.symbol_url == symbol_url and cs.logo_url == logo_url:
        skipped += 1
        continue

    cs.symbol_url = symbol_url
    cs.logo_url = logo_url
    to_update.append(cs)
    updated += 1

CardSet.objects.bulk_update(to_update, ['symbol_url', 'logo_url'])

print(f"Updated: {updated}")
print(f"Already correct: {skipped}")
print(f"Not in map: {len(not_mapped)} — {not_mapped}")
