"""
Fix remaining set symbol URLs for sets with different DB codes
Run: python manage.py shell --command="exec(open('populate_set_symbols2.py').read())"
"""
from products.models import CardSet

EXTRA_MAP = {
    # SM sets with different codes in DB
    'SUM':    'sm1',   'GRI':    'sm2',   'BUS':    'sm3',
    'SLG':    'sm35',  'CIN':    'sm4',   'UPR':    'sm5',
    'FLI':    'sm6',   'LOT':    'sm8',   'TEU':    'sm9',
    'DET':    'det1',  'UNB':    'sm10',  'UNM':    'sm11',
    'SMA':    'sma',   'CEC':    'sm12',
    # SwSh sets with different codes
    'SSH':    'swsh1', 'RCL':    'swsh2', 'DAA':    'swsh3',
    'CPA':    'swsh35','VIV':    'swsh4', 'CRE':    'swsh6',
    'EVS':    'swsh7', 'CEL':    'cel25', 'CELCC':  'cel25c',
    'FST':    'swsh8', 'BRS':    'swsh9', 'ASR':    'swsh10',
    'LOR':    'swsh11','SIT':    'swsh12',
    # Trainer Galleries with different codes
    'BRSTG':  'swsh9tg', 'SITTG': 'swsh12tg',
    # SV sets with different codes
    'SV1':    'sv1',   'SV2':    'sv2',   'SV3':    'sv3',
    'SV3PT5': 'sv3pt5','SV4':    'sv4',   'SV4PT5': 'sv4pt5',
    # Promos
    'PR-SW':  'swshp', 'PR-SV':  'svp',   'PR-DPP': 'dpp',
    'PR-NB':  'np',    'PR-NP':  'np',
    # Other
    'CL':     'col1',  'B2':     'base4',
    'PR-SW':  'swshp',
}

BASE_URL = "https://images.pokemontcg.io"
updated = 0
not_found = []

for code, ptcgio_id in EXTRA_MAP.items():
    try:
        cs = CardSet.objects.get(code=code)
        cs.symbol_url = f"{BASE_URL}/{ptcgio_id}/symbol.png"
        cs.logo_url   = f"{BASE_URL}/{ptcgio_id}/logo.png"
        cs.save()
        updated += 1
        print(f"  {code:<12} -> {ptcgio_id}")
    except CardSet.DoesNotExist:
        not_found.append(code)

print(f"\nUpdated: {updated}")
print(f"Not in DB: {not_found}")
