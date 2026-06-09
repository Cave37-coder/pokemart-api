"""
Check ALL variant records against TCGCSV prices.
For each card's productId, fetch the price rows and determine valid variants.
Flag any DB record whose variant has no matching price row.

SKIPS WotC B1/B2 sets - they have 1st Edition + Unlimited N variants (legitimate multiple N).
"""
import os
import django
import requests
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct

HEADERS = {"User-Agent": "PokeBulkSA/1.0"}
TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"

# WotC era - skip entirely
WOTC_SETS = {
    "BS","BS2","FO","JU","TR","G1","G2","N1","N2","N3","N4",
    "LC","BSS","SI1","EX","AQ","SK","RS","SS","DR","MA","HL",
    "RG","TRR","EM","UF","DS","LM","HP","CG","DF","PK","DX",
    "DP","MT","SW","GE","MD","LA","SF","PL","RR","AR",
    "HS","UL","UD","TM","CoL",
}

# Map TCGCSV subTypeName -> variant_override code
SUBTYPE_TO_VARIANT = {
    "Normal": "N",
    "Unlimited Normal": "N",
    "1st Edition Normal": "N",
    "Holofoil": "H",
    "Unlimited Holofoil": "H",
    "1st Edition Holofoil": "H",
    "Reverse Holofoil": "RH",
    "Poke Ball": "PB",
    "Master Ball": "MB",
    "Love Ball": "LB",
    "Friend Ball": "FB",
    "Quick Ball": "QB",
    "Ultra Ball": "UB",
    "Dusk Ball": "DB",
    "Team Rocket": "TR",
    "Special": "SE",
    "Poke Ball Pattern": "PBP",
    "Master Ball Pattern": "MBP",
    "Code Card": "CC",
    "": "H",  # empty subtype defaults to H
}

GROUP_CONFIG = {
    "BLW":(1400,"B4"),"EPO":(1424,"B4"),"NVI":(1385,"B4"),"NXD":(1412,"B4"),
    "DEX":(1386,"B4"),"DRX":(1394,"B4"),"BCR":(1408,"B4"),
    "PLS":(1413,"B4"),"PLF":(1382,"B4"),"PLB":(1370,"B4"),"LTR":(1409,"B4"),
    "KSS":(1522,"B5"),"XY":(1387,"B5"),"FLF":(1464,"B5"),"FFI":(1481,"B5"),
    "PHF":(1494,"B5"),"PRC":(1509,"B5"),"DCR":(1525,"B5"),"ROS":(1534,"B5"),
    "AOR":(1576,"B5"),"BKT":(1661,"B5"),"BKP":(1701,"B5"),"GEN":(1728,"B5"),
    "FCO":(1780,"B5"),"STS":(1815,"B5"),"EVO":(1842,"B5"),
    "SM01":(1863,"B6"),"SM02":(1919,"B6"),"SM03":(1957,"B6"),"SHL":(2054,"B6"),
    "SM04":(2071,"B6"),"SM05":(2178,"B6"),"SM06":(2209,"B6"),"CES":(2278,"B6"),
    "DRM":(2295,"B6"),"SM8":(2328,"B6"),"SM9":(2377,"B6"),"SM10":(2420,"B6"),
    "SM11":(2464,"B6"),"HIF":(2480,"B6"),"SM12":(2534,"B6"),
    "SWSH01":(2585,"B7"),"SWSH02":(2626,"B7"),"SWSH03":(2675,"B7"),
    "CHP":(2685,"B7"),"SWSH04":(2701,"B7"),
    "SWSH05":(2765,"B7"),"SWSH06":(2807,"B7"),"SWSH07":(2848,"B7"),
    "CLB":(2867,"B7"),"SWSH08":(2906,"B7"),
    "SWSH09":(2948,"B7"),"SWSH10":(3040,"B7"),"PGO":(3064,"B7"),
    "SWSH11":(3118,"B7"),"SWSH12":(3170,"B7"),"CRZ":(17688,"B7"),
    "TK22":(3179,"B7"),"TK23":(23266,"B8"),"TK24":(23561,"B8"),
    "SVP":(22872,"B8"),"SVI":(22873,"B8"),"PAL":(23120,"B8"),
    "OBF":(23228,"B8"),"MEW":(23237,"B8"),"PAR":(23286,"B8"),
    "PAF":(23353,"B8"),"TEF":(23381,"B8"),"TWM":(23473,"B8"),
    "SFA":(23529,"B8"),"SCR":(23537,"B8"),"SSP":(23651,"B8"),
    "PRE":(23821,"B8"),"JTG":(24073,"B8"),"DRI":(24269,"B8"),
    "BLK":(24325,"B8"),"WHT":(24326,"B8"),
    "PRIZEPACK":(22880,"B8"),
    "MEG":(24380,"B9"),"PFL":(24448,"B9"),"ASC":(24541,"B9"),
    "POR":(24587,"B9"),"CRI":(24655,"B9"),
}

# Get all sets with products, excluding WotC
all_sets = PokemonProduct.objects.filter(
    tcgcsv_product_id__isnull=False
).values_list('card_set__code', flat=True).distinct()

sets_to_check = [s for s in sorted(set(all_sets)) if s not in WOTC_SETS]

wrong_ids = []
print(f"Checking {len(sets_to_check)} sets against TCGCSV prices...\n")

for set_code in sets_to_check:
    if set_code not in GROUP_CONFIG:
        print(f"SKIP {set_code} - not in GROUP_CONFIG")
        continue

    group_id = GROUP_CONFIG[set_code][0]

    try:
        r = requests.get(f"{TCGCSV_BASE}/{group_id}/prices", headers=HEADERS, timeout=30)
        r.raise_for_status()
        price_rows = r.json().get("results", [])
    except Exception as e:
        print(f"FAIL {set_code} (group {group_id}): {e}")
        continue

    # Build: productId -> set of valid variant codes
    valid_variants = {}
    for row in price_rows:
        pid = row.get("productId")
        sub = row.get("subTypeName", "")
        variant = SUBTYPE_TO_VARIANT.get(sub)
        if variant and pid:
            if pid not in valid_variants:
                valid_variants[pid] = set()
            valid_variants[pid].add(variant)

    # Check every card in this set
    cards = PokemonProduct.objects.filter(
        card_set__code=set_code,
        tcgcsv_product_id__isnull=False
    )

    # Variants that are always legitimate regardless of TCGCSV pricing
    EXEMPT_VARIANTS = {"PB","MB","LB","FB","QB","UB","DB","TR","SE","PBP","MBP","CC","TT"}

    wrong_in_set = []
    for card in cards:
        pid = card.tcgcsv_product_id
        v = card.variant_override
        if v in EXEMPT_VARIANTS:
            continue
        allowed = valid_variants.get(pid, set())
        if allowed and v not in allowed:
            wrong_in_set.append(card.id)
            wrong_ids.append(card.id)

    if wrong_in_set:
        print(f"{set_code}: {len(wrong_in_set)} wrong variants")
    else:
        print(f"{set_code}: OK")

    time.sleep(0.2)

print(f"\nTotal wrong variants to delete: {len(wrong_ids)}")
with open("wrong_n_ids.txt", "w") as f:
    f.write("\n".join(str(i) for i in wrong_ids))
print("Saved to wrong_n_ids.txt")
