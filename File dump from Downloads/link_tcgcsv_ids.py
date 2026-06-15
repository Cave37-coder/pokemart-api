import os, sys, django, time, unicodedata
from decimal import Decimal

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, "C:/Users/texca/pokemart-api")
django.setup()

import requests
from django.db import transaction
from products.models import PokemonProduct, CardSet

HEADERS = {"User-Agent": "PokeBulkSA/1.0"}
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/USD"
MARKUP = Decimal("1.1")

import math
def round_up_50c(zar):
    return Decimal(math.ceil(float(zar) * 2)) / 2

def to_zar(usd, rate):
    return round_up_50c(Decimal(str(usd)) * rate * MARKUP)

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")

def norm_name(name):
    return strip_accents(name.strip().lower())

def norm_num(raw):
    return str(raw or "").split("/")[0].lstrip("0") or "0"

# TCGCSV subTypeName -> variant_override mapping
SUBTYPE_TO_VARIANT = {
    "Normal":           "N",
    "Holofoil":         "H",
    "Reverse Holofoil": "RH",
    "1st Edition Normal": "N",
    "1st Edition Holofoil": "H",
    "Unlimited Normal": "N",
    "Unlimited Holofoil": "H",
    "":                 "N",  # no subtype = single variant (TG, GG, Prize Pack)
}

# TCGCSV groupId -> DB CardSet code mapping
GROUP_TO_DB = {}

def build_group_map():
    """Map TCGCSV groupIds to DB CardSet codes"""
    sets = CardSet.objects.all()
    # Build by abbreviation first
    abbr_map = {}
    for cs in sets:
        abbr_map[cs.code.upper()] = cs
    
    groups = requests.get("https://tcgcsv.com/tcgplayer/3/groups", headers=HEADERS).json()
    groups = groups.get("results", groups) if isinstance(groups, dict) else groups
    
    # Manual mappings for known mismatches
    MANUAL = {
        604:   "BS",    # Base Set
        605:   "B2",    # Base Set 2
        630:   "FO",    # Fossil
        635:   "JU",    # Jungle
        648:   "SI1",   # Southern Islands
        1367:  "RR",    # Rising Rivals
        1368:  "MT",    # Mysterious Treasures
        1369:  "SF",    # Stormfront
        1370:  "PLB",   # Plasma Blast
        1372:  "SK",    # Skyridge
        1373:  "TR",    # Team Rocket
        1374:  "LC",    # Legendary Collection
        1375:  "EX",    # Expedition
        1376:  "DR",    # Dragon
        1377:  "MA",    # Team Magma vs Team Aqua
        1378:  "LM",    # Legend Maker
        1379:  "HP",    # Holon Phantoms
        1380:  "SW",    # Secret Wonders
        1381:  "TM",    # Triumphant
        1382:  "PLF",   # Plasma Freeze
        1383:  "PK",    # Power Keepers
        1384:  "SV",    # Supreme Victors
        1385:  "NVI",   # Noble Victories
        1386:  "DEX",   # Dark Explorers
        1387:  "XY",    # XY Base Set
        1389:  "N3",    # Neo Revelation
        1390:  "MD",    # Majestic Dawn
        1391:  "AR",    # Arceus
        1392:  "SS",    # Sandstorm
        1393:  "RS",    # Ruby & Sapphire
        1394:  "DRX",   # Dragons Exalted
        1395:  "CG",    # Crystal Guardians
        1396:  "N1",    # Neo Genesis
        1397:  "AQ",    # Aquapolis
        1398:  "UF",    # Unseen Forces
        1399:  "UL",    # Unleashed
        1400:  "BLW",   # Black & White
        1402:  "HS",    # HeartGold SoulSilver
        1403:  "UD",    # Undaunted
        1404:  "DX",    # Deoxys
        1405:  "GE",    # Great Encounters
        1406:  "PL",    # Platinum
        1408:  "BCR",   # Boundaries Crossed
        1409:  "LTR",   # Legendary Treasures
        1410:  "EM",    # Emerald
        1411:  "DF",    # Dragon Frontiers
        1412:  "NXD",   # Next Destinies
        1413:  "PLS",   # Plasma Storm
        1415:  "CL",    # Call of Legends
        1416:  "HL",    # Hidden Legends
        1417:  "LA",    # Legends Awakened
        1419:  "RG",    # FireRed & LeafGreen
        1424:  "EPO",   # Emerging Powers
        1426:  "DRV",   # Dragon Vault
        1428:  "TRR",   # Team Rocket Returns
        1429:  "DS",    # Delta Species
        1430:  "DP",    # Diamond & Pearl
        1432:  "POP6",  # POP Series 6
        1434:  "N2",    # Neo Discovery
        1439:  "POP5",  # POP Series 5
        1440:  "G2",    # Gym Challenge
        1441:  "G1",    # Gym Heroes
        1442:  "POP3",  # POP Series 3
        1444:  "N4",    # Neo Destiny
        1446:  "POP9",  # POP Series 9
        1447:  "POP2",  # POP Series 2
        1450:  "POP8",  # POP Series 8
        1452:  "POP4",  # POP Series 4
        1464:  "FLF",   # Flashfire
        1481:  "FFI",   # Furious Fists
        1494:  "PHF",   # Phantom Forces
        1509:  "PRC",   # Primal Clash
        1525:  "DCR",   # Double Crisis
        1534:  "ROS",   # Roaring Skies
        1576:  "AOR",   # Ancient Origins
        1661:  "BKT",   # BREAKthrough
        1701:  "BKP",   # BREAKpoint
        1728:  "GEN",   # Generations
        1780:  "FCO",   # Fates Collide
        1815:  "STS",   # Steam Siege
        1842:  "EVO",   # Evolutions
        1861:  "PR-SM", # SM Promos
        1863:  "SUM",   # Sun & Moon Base
        1919:  "GRI",   # Guardians Rising
        1957:  "BUS",   # Burning Shadows
        2054:  "SLG",   # Shining Legends
        2071:  "CIN",   # Crimson Invasion
        2178:  "UPR",   # Ultra Prism
        2209:  "FLI",   # Forbidden Light
        2278:  "CES",   # Celestial Storm
        2295:  "DRM",   # Dragon Majesty
        2328:  "LOT",   # Lost Thunder
        2377:  "TEU",   # Team Up
        2409:  "DET",   # Detective Pikachu
        2420:  "UNB",   # Unbroken Bonds
        2464:  "UNM",   # Unified Minds
        2480:  "HIF",   # Hidden Fates
        2534:  "CEC",   # Cosmic Eclipse
        2545:  "PR-SW", # SWSH Promos
        2585:  "SSH",   # Sword & Shield
        2594:  "SMA",   # Hidden Fates Shiny Vault
        2626:  "RCL",   # Rebel Clash
        2675:  "DAA",   # Darkness Ablaze
        2685:  "CPA",   # Champions Path
        2701:  "VIV",   # Vivid Voltage
        2754:  "SHF",   # Shining Fates
        2765:  "BST",   # Battle Styles
        2807:  "CRE",   # Chilling Reign
        2848:  "EVS",   # Evolving Skies
        2867:  "CEL",   # Celebrations
        2906:  "FST",   # Fusion Strike
        2948:  "BRS",   # Brilliant Stars
        3020:  "BRSTG", # BRS Trainer Gallery - NOT IN DB YET
        3040:  "ASR",   # Astral Radiance
        3064:  "PGO",   # Pokemon GO
        3068:  "ASRTG", # ASR Trainer Gallery - NOT IN DB YET
        3118:  "LOR",   # Lost Origin
        3150:  "MCD22", # McDonalds 2022
        3170:  "SIT",   # Silver Tempest
        3172:  "LORTG", # LOR Trainer Gallery - NOT IN DB YET
        17674: "SITTG", # SIT Trainer Gallery - NOT IN DB YET
        17688: "CRZ",   # Crown Zenith
        17689: "CRZGG", # Crown Zenith Galarian Gallery - NOT IN DB YET
        22872: "SVP",   # SV Promos
        22873: "SV1",   # Scarlet & Violet
        22880: "PRIZEPACK", # Prize Pack - NOT IN DB YET
        23120: "SV2",   # Paldea Evolved
        23228: "SV3",   # Obsidian Flames
        23237: "SV3PT5",# 151
        23286: "SV4",   # Paradox Rift
        23306: "MCD23", # McDonalds 2023 - NOT IN DB YET
        23353: "SV4PT5",# Paldean Fates
        23381: "TEF",   # Temporal Forces
        23473: "TWM",   # Twilight Masquerade
        23529: "SFA",   # Shrouded Fable
        23537: "SCR",   # Stellar Crown
        23651: "SSP",   # Surging Sparks
        23821: "PRE",   # Prismatic Evolutions
        24073: "JTG",   # Journey Together
        24163: "MCD24", # McDonalds 2024 - NOT IN DB YET
        24269: "DRI",   # Destined Rivals
        24325: "BLK",   # Black Bolt
        24326: "WHT",   # White Flare
        24380: "MEG",   # Mega Evolution
        24382: "SVE",   # SV Energies - NOT IN DB YET
        24448: "PFL",   # Phantasmal Flames
        24451: "MEP",   # Mega Evolution Promos - NOT IN DB YET
        24541: "ASC",   # Ascended Heroes
        24587: "POR",   # Perfect Order
        24655: "CRI",   # Chaos Rising - NOT IN DB YET
        24688: "ME05",  # Pitch Black - NOT IN DB YET
        1401:  "MCD11", # McDonalds 2011
        1427:  "MCD12", # McDonalds 2012
        1692:  "MCD14", # McDonalds 2014
        1694:  "MCD15", # McDonalds 2015
        3087:  "MCD16", # McDonalds 2016
        2148:  "MCD17", # McDonalds 2017
        2364:  "MCD18", # McDonalds 2018
        2555:  "MCD19", # McDonalds 2019
        2782:  "MCD21", # McDonalds 25th Anniversary
        1414:  "POP7",  # POP Series 7
        1422:  "POP1",  # POP Series 1
        2781:  "SHFSV", # Shining Fates Shiny Vault
        1663:  "BSS",   # Base Set Shadowless - NOT IN DB
        1729:  "GENRC", # Generations Radiant Collection - NOT IN DB
        1465:  "LTRRC", # LTR Radiant Collection - NOT IN DB
    }
    
    result = {}
    for g in groups:
        gid = g.get("groupId") or g.get("id")
        db_code = MANUAL.get(gid)
        if db_code:
            cs = CardSet.objects.filter(code=db_code).first()
            if cs:
                result[gid] = cs
    
    return result, groups

def link_tcgcsv_ids():
    """Main function: link TCGCSV productIds to DB cards and set prices"""
    print("Fetching USD->ZAR rate...")
    rate_data = requests.get(EXCHANGE_RATE_API).json()
    rate = Decimal(str(rate_data["rates"]["ZAR"]))
    print(f"Rate: 1 USD = R{rate}")
    
    print("\nBuilding group map...")
    group_map, all_groups = build_group_map()
    print(f"Mapped {len(group_map)} TCGCSV groups to DB sets")
    
    total_linked = 0
    total_priced = 0
    total_unmatched = 0
    
    for gid, cs in sorted(group_map.items()):
        print(f"\n[{cs.code}] group={gid} - {cs.name}")
        
        # Fetch products (cards only)
        prods = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/products", headers=HEADERS).json()
        prods = prods.get("results", prods) if isinstance(prods, dict) else prods
        cards = [p for p in prods if any(e.get("name") == "Number" for e in p.get("extendedData", []))]
        
        # Fetch prices
        prices = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/prices", headers=HEADERS).json()
        prices = prices.get("results", prices) if isinstance(prices, dict) else prices
        time.sleep(0.3)
        
        # Build price lookup: productId -> {subTypeName -> marketPrice}
        price_by_pid = {}
        for pr in prices:
            pid = pr.get("productId")
            sub = pr.get("subTypeName", "") or ""
            usd = pr.get("marketPrice") or pr.get("midPrice") or pr.get("lowPrice")
            if pid and usd:
                if pid not in price_by_pid:
                    price_by_pid[pid] = {}
                price_by_pid[pid][sub] = Decimal(str(usd))
        
        # Build DB card lookup: (norm_name, norm_num) -> list of products
        db_cards = list(PokemonProduct.objects.filter(card_set=cs))
        db_lookup = {}
        for card in db_cards:
            key = (norm_name(card.name.split(" (")[0]), norm_num(card.card_number))
            if key not in db_lookup:
                db_lookup[key] = []
            db_lookup[key].append(card)
        
        linked = 0
        priced = 0
        unmatched = 0
        updates = []
        
        for tcg_prod in cards:
            pid = tcg_prod.get("productId")
            tcg_name = tcg_prod.get("name", "").strip()
            ext = {e["name"]: e["value"] for e in tcg_prod.get("extendedData", [])}
            tcg_num = norm_num(ext.get("Number", ""))
            
            key = (norm_name(tcg_name), tcg_num)
            db_matches = db_lookup.get(key, [])
            
            if not db_matches:
                unmatched += 1
                continue
            
            # Get prices for this productId
            pid_prices = price_by_pid.get(pid, {})
            
            for db_card in db_matches:
                # Determine which subType matches this card's variant
                variant = db_card.variant_override or "N"
                
                # Map variant to TCGCSV subTypeName
                if variant in ("N",):
                    sub = "Normal"
                elif variant in ("H", "RH-H", "SH-H"):
                    sub = "Holofoil"
                elif variant in ("RH", "ERH", "BRH-PB", "BRH-MB", "BRH-FB", "BRH-LB", "BRH-QB", "BRH-DB", "BRH-R", "TRH"):
                    sub = "Reverse Holofoil"
                elif variant in ("EX", "GX", "V", "VMAX", "IR", "SIR", "HR", "DR", "AS"):
                    sub = "Holofoil"
                else:
                    sub = "Normal"
                
                usd = pid_prices.get(sub)
                if not usd:
                    # Try any available price
                    usd = next(iter(pid_prices.values()), None)
                
                changed = False
                if db_card.tcgcsv_product_id != pid:
                    db_card.tcgcsv_product_id = pid
                    changed = True
                    linked += 1
                
                if usd and (not db_card.price or db_card.price == 0):
                    db_card.price = to_zar(usd, rate)
                    changed = True
                    priced += 1
                
                if changed:
                    updates.append(db_card)
        
        if updates:
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(updates, ["tcgcsv_product_id", "price"])
        
        total_linked += linked
        total_priced += priced
        total_unmatched += unmatched
        print(f"  linked={linked} priced={priced} unmatched={unmatched}")
    
    print(f"\n{'='*60}")
    print(f"DONE: linked={total_linked} priced={total_priced} unmatched={total_unmatched}")

if __name__ == "__main__":
    link_tcgcsv_ids()
