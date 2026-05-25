"""
PokéBulk SA — Bible CSV Generator
Run locally weekly to generate the master pricing CSV.
Usage: python pokebulk_csv_download.py
Output: pokebulk_cards_YYYYMMDD.csv in the same folder
"""

import csv
import math
import time
import requests
import re
from datetime import datetime
from decimal import Decimal, ROUND_UP

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")
MIN_ZAR = Decimal("1.50")

RATE_APIS = [
    "https://api.exchangerate-api.com/v4/latest/USD",
    "https://open.er-api.com/v6/latest/USD",
]

# CSV columns — same as existing bible + 2 new at end
COLUMNS = [
    'era', 'set_name', 'abbreviation', 'group_id', 'productId',
    'name', 'cleanName', 'number', 'rarity', 'cardType', 'hp',
    'stage', 'artist', 'isCard', 'subTypeName',
    'market_usd', 'low_usd', 'mid_usd', 'high_usd', 'direct_low_usd',
    'usd_zar_rate', 'pokebulk_zar', 'tcgplayer_url',
    'name_pattern', 'db_variant',
]

# Name pattern → DB variant mapping (bible)
PATTERN_TO_VARIANT = {
    # ASC ball patterns
    'Energy Symbol Pattern': 'ERH',
    'Poke Ball':             'BRH-PB',
    'Friend Ball':           'BRH-FB',
    'Love Ball':             'BRH-LB',
    'Quick Ball':            'BRH-QB',
    'Dusk Ball':             'BRH-DB',
    'Team Rocket':           'TRH',
    # PRE/BLK/WHT patterns
    'Poke Ball Pattern':     'BRH-PB',
    'Master Ball Pattern':   'RH-MB',
    'Holiday Calendar':      'H',
    # Cosmetic holos — same price class
    'Cosmos Holo':           'H',
    'Cosmo Holo':            'H',
    'Cosmos Holofoil':       'H',
    'Cosmo Holofoil':        'H',
    'Cracked Ice Holo':      'H',
    # Base era
    'Red Cheeks':            'N',
    'Black Dot Error':       'H',
    # Delta Species etc — same price class
    'Delta Species':         None,  # inherits subtype
    'Exclusive':             None,
    '151 Metal Card':        'H',
}

# subTypeName → DB variant (standard mapping)
SUBTYPE_TO_VARIANT = {
    'Normal':               'N',
    'Holofoil':             'H',
    'Reverse Holofoil':     'RH',
    '1st Edition':          '1E',
    '1st Edition Holofoil': '1E-H',
    'Unlimited':            'N',
    'Unlimited Holofoil':   'H',
    '':                     'H',
}

# Era names
ERA_NAMES = {
    'B1': 'Base Era',
    'B2': 'EX Era',
    'B3': 'DP / HGSS Era',
    'B4': 'Black & White Era',
    'B5': 'XY Era',
    'B6': 'Sun & Moon Era',
    'B7': 'Sword & Shield Era',
    'B8': 'Scarlet & Violet Era',
    'B9': 'Mega Evolution Era',
}

# Complete GROUP_CONFIG — all sets
GROUP_CONFIG = {
    # Base Era (B1)
    "BS":       (604,   "Base Set",                             "B1"),
    "BS2":      (605,   "Base Set 2",                          "B1"),
    "FO":       (630,   "Fossil",                              "B1"),
    "JU":       (635,   "Jungle",                              "B1"),
    "SI1":      (648,   "Southern Islands",                    "B1"),
    "TR":       (1373,  "Team Rocket",                         "B1"),
    "G1":       (1441,  "Gym Heroes",                          "B1"),
    "G2":       (1440,  "Gym Challenge",                       "B1"),
    "N1":       (1396,  "Neo Genesis",                         "B1"),
    "N2":       (1434,  "Neo Discovery",                       "B1"),
    "N3":       (1389,  "Neo Revelation",                      "B1"),
    "N4":       (1444,  "Neo Destiny",                         "B1"),
    "LC":       (1374,  "Legendary Collection",                "B1"),
    "BSS":      (1663,  "Base Set (Shadowless)",               "B1"),
    "PR-WB":    (1418,  "WoTC Black Star Promos",              "B1"),
    "PR-BEST":  (1455,  "Best of Game Promos",                 "B1"),
    # EX Era (B2)
    "EX":       (1375,  "Expedition Base Set",                 "B2"),
    "AQ":       (1397,  "Aquapolis",                           "B2"),
    "SK":       (1372,  "Skyridge",                            "B2"),
    "RS":       (1393,  "Ruby and Sapphire",                   "B2"),
    "SS":       (1392,  "Sandstorm",                           "B2"),
    "DR":       (1376,  "Dragon",                              "B2"),
    "MA":       (1377,  "Team Magma vs Team Aqua",             "B2"),
    "HL":       (1416,  "Hidden Legends",                      "B2"),
    "RG":       (1419,  "FireRed & LeafGreen",                 "B2"),
    "TRR":      (1428,  "Team Rocket Returns",                 "B2"),
    "DS":       (1429,  "Delta Species",                       "B2"),
    "EM":       (1410,  "Emerald",                             "B2"),
    "UF":       (1398,  "Unseen Forces",                       "B2"),
    "DF":       (1411,  "Dragon Frontiers",                    "B2"),
    "CG":       (1395,  "Crystal Guardians",                   "B2"),
    "HP":       (1379,  "Holon Phantoms",                      "B2"),
    "LM":       (1378,  "Legend Maker",                        "B2"),
    "PK":       (1383,  "Power Keepers",                       "B2"),
    "PR-NB":    (1423,  "Nintendo Black Star Promos",          "B2"),
    "POP1":     (1422,  "POP Series 1",                        "B2"),
    "POP2":     (1447,  "POP Series 2",                        "B2"),
    "POP3":     (1442,  "POP Series 3",                        "B2"),
    "POP4":     (1452,  "POP Series 4",                        "B2"),
    # DP / HGSS Era (B3)
    "DP":       (1430,  "Diamond and Pearl",                   "B3"),
    "MT":       (1368,  "Mysterious Treasures",                "B3"),
    "SW":       (1380,  "Secret Wonders",                      "B3"),
    "GE":       (1405,  "Great Encounters",                    "B3"),
    "MD":       (1390,  "Majestic Dawn",                       "B3"),
    "LA":       (1417,  "Legends Awakened",                    "B3"),
    "SF":       (1369,  "Stormfront",                          "B3"),
    "PL":       (1406,  "Platinum",                            "B3"),
    "RR":       (1367,  "Rising Rivals",                       "B3"),
    "SV":       (1384,  "Supreme Victors",                     "B3"),
    "AR":       (1391,  "Arceus",                              "B3"),
    "HS":       (1402,  "HeartGold SoulSilver",                "B3"),
    "UL":       (1399,  "Unleashed",                           "B3"),
    "UD":       (1403,  "Undaunted",                           "B3"),
    "TM":       (1381,  "Triumphant",                          "B3"),
    "CoL":      (1415,  "Call of Legends",                     "B3"),
    "RUM":      (1433,  "Rumble",                              "B3"),
    "PR-DP":    (1421,  "DP Black Star Promos",                "B3"),
    "PR-HS":    (1453,  "HGSS Black Star Promos",              "B3"),
    "POP5":     (1439,  "POP Series 5",                        "B3"),
    "POP6":     (1432,  "POP Series 6",                        "B3"),
    "POP7":     (1414,  "POP Series 7",                        "B3"),
    "POP8":     (1450,  "POP Series 8",                        "B3"),
    "POP9":     (1446,  "POP Series 9",                        "B3"),
    # Black & White Era (B4)
    "BLW":      (1400,  "Black and White",                     "B4"),
    "EPO":      (1424,  "Emerging Powers",                     "B4"),
    "NVI":      (1385,  "Noble Victories",                     "B4"),
    "NXD":      (1412,  "Next Destinies",                      "B4"),
    "DEX":      (1386,  "Dark Explorers",                      "B4"),
    "DRX":      (1394,  "Dragons Exalted",                     "B4"),
    "DRV":      (1426,  "Dragon Vault",                        "B4"),
    "BCR":      (1408,  "Boundaries Crossed",                  "B4"),
    "PLS":      (1413,  "Plasma Storm",                        "B4"),
    "PLF":      (1382,  "Plasma Freeze",                       "B4"),
    "PLB":      (1370,  "Plasma Blast",                        "B4"),
    "LTR":      (1409,  "Legendary Treasures",                 "B4"),
    "LTRRC":    (1465,  "Legendary Treasures: Radiant Collection","B4"),
    "PR-BLW":   (1407,  "BW Black Star Promos",                "B4"),
    "MCD11":    (1401,  "McDonald's Collection 2011",          "B4"),
    "MCD12":    (1427,  "McDonald's Collection 2012",          "B4"),
    # XY Era (B5)
    "KSS":      (1522,  "Kalos Starter Set",                   "B5"),
    "XY":       (1387,  "XY Base Set",                         "B5"),
    "FLF":      (1464,  "Flashfire",                           "B5"),
    "FFI":      (1481,  "Furious Fists",                       "B5"),
    "PHF":      (1494,  "Phantom Forces",                      "B5"),
    "PRC":      (1509,  "Primal Clash",                        "B5"),
    "DCR":      (1525,  "Double Crisis",                       "B5"),
    "ROS":      (1534,  "Roaring Skies",                       "B5"),
    "AOR":      (1576,  "Ancient Origins",                     "B5"),
    "BKT":      (1661,  "BREAKthrough",                        "B5"),
    "BKP":      (1701,  "BREAKpoint",                          "B5"),
    "GEN":      (1728,  "Generations",                         "B5"),
    "GENRC":    (1729,  "Generations: Radiant Collection",     "B5"),
    "FCO":      (1780,  "Fates Collide",                       "B5"),
    "STS":      (1815,  "Steam Siege",                         "B5"),
    "EVO":      (1842,  "Evolutions",                          "B5"),
    "PR-XY":    (1451,  "XY Black Star Promos",                "B5"),
    "MCD14":    (1692,  "McDonald's Collection 2014",          "B5"),
    "MCD15":    (1694,  "McDonald's Collection 2015",          "B5"),
    "MCD16":    (3087,  "McDonald's Collection 2016",          "B5"),
    # Sun & Moon Era (B6)
    "SM01":     (1863,  "Sun & Moon",                          "B6"),
    "SM02":     (1919,  "Guardians Rising",                    "B6"),
    "SM03":     (1957,  "Burning Shadows",                     "B6"),
    "SHL":      (2054,  "Shining Legends",                     "B6"),
    "SM04":     (2071,  "Crimson Invasion",                    "B6"),
    "SM05":     (2178,  "Ultra Prism",                         "B6"),
    "SM06":     (2209,  "Forbidden Light",                     "B6"),
    "CES":      (2278,  "Celestial Storm",                     "B6"),
    "DRM":      (2295,  "Dragon Majesty",                      "B6"),
    "SM8":      (2328,  "Lost Thunder",                        "B6"),
    "SM9":      (2377,  "Team Up",                             "B6"),
    "DEP":      (2409,  "Detective Pikachu",                   "B6"),
    "SM10":     (2420,  "Unbroken Bonds",                      "B6"),
    "SM11":     (2464,  "Unified Minds",                       "B6"),
    "HIF":      (2480,  "Hidden Fates",                        "B6"),
    "HIFSV":    (2594,  "Hidden Fates: Shiny Vault",           "B6"),
    "SM12":     (2534,  "Cosmic Eclipse",                      "B6"),
    "PR-SM":    (1861,  "SM Black Star Promos",                "B6"),
    "MCD17":    (2148,  "McDonald's Collection 2017",          "B6"),
    "MCD18":    (2364,  "McDonald's Collection 2018",          "B6"),
    "MCD19":    (2555,  "McDonald's Collection 2019",          "B6"),
    # Sword & Shield Era (B7)
    "SWSH01":   (2585,  "Sword & Shield",                      "B7"),
    "SWSH02":   (2626,  "Rebel Clash",                         "B7"),
    "SWSH03":   (2675,  "Darkness Ablaze",                     "B7"),
    "CHP":      (2685,  "Champion's Path",                     "B7"),
    "SWSH04":   (2701,  "Vivid Voltage",                       "B7"),
    "SHF":      (2754,  "Shining Fates",                       "B7"),
    "SHFSV":    (2781,  "Shining Fates: Shiny Vault",          "B7"),
    "SWSH05":   (2765,  "Battle Styles",                       "B7"),
    "MCD21":    (2782,  "McDonald's 25th Anniversary",         "B7"),
    "SWSH06":   (2807,  "Chilling Reign",                      "B7"),
    "SWSH07":   (2848,  "Evolving Skies",                      "B7"),
    "CLB":      (2867,  "Celebrations",                        "B7"),
    "CCC":      (2931,  "Celebrations: Classic Collection",    "B7"),
    "SWSH08":   (2906,  "Fusion Strike",                       "B7"),
    "SWSH09":   (2948,  "Brilliant Stars",                     "B7"),
    "BST":      (3020,  "Brilliant Stars Trainer Gallery",     "B7"),
    "SWSH10":   (3040,  "Astral Radiance",                     "B7"),
    "PGO":      (3064,  "Pokemon GO",                          "B7"),
    "ASRTG":    (3068,  "Astral Radiance Trainer Gallery",     "B7"),
    "SWSH11":   (3118,  "Lost Origin",                         "B7"),
    "LORTG":    (3172,  "Lost Origin Trainer Gallery",         "B7"),
    "SWSH12":   (3170,  "Silver Tempest",                      "B7"),
    "ST":       (17674, "Silver Tempest Trainer Gallery",      "B7"),
    "CRZ":      (17688, "Crown Zenith",                        "B7"),
    "CRZGG":    (17689, "Crown Zenith: Galarian Gallery",      "B7"),
    "TOT22":    (3179,  "Trick or Trade 2022",                 "B7"),
    "MCD22":    (3150,  "McDonald's Collection 2022",          "B7"),
    "PR-SWSH":  (2545,  "SWSH Black Star Promos",              "B7"),
    # Scarlet & Violet Era (B8)
    "SVP":      (22872, "Scarlet & Violet Promos",             "B8"),
    "SVI":      (22873, "Scarlet & Violet",                    "B8"),
    "PRIZEPACK":(22880, "Prize Pack Series",                   "B8"),
    "PAL":      (23120, "Paldea Evolved",                      "B8"),
    "OBF":      (23228, "Obsidian Flames",                     "B8"),
    "MEW":      (23237, "Scarlet & Violet 151",                "B8"),
    "TOT23":    (23266, "Trick or Trade 2023",                 "B8"),
    "PAR":      (23286, "Paradox Rift",                        "B8"),
    "MCD23":    (23306, "McDonald's Collection 2023",          "B8"),
    "TCGCL":    (23323, "Trading Card Game Classic",           "B8"),
    "PAF":      (23353, "Paldean Fates",                       "B8"),
    "TEF":      (23381, "Temporal Forces",                     "B8"),
    "TWM":      (23473, "Twilight Masquerade",                 "B8"),
    "SFA":      (23529, "Shrouded Fable",                      "B8"),
    "SCR":      (23537, "Stellar Crown",                       "B8"),
    "TOT24":    (23561, "Trick or Trade 2024",                 "B8"),
    "SSP":      (23651, "Surging Sparks",                      "B8"),
    "PRE":      (23821, "Prismatic Evolutions",                "B8"),
    "JTG":      (24073, "Journey Together",                    "B8"),
    "MCD24":    (24163, "McDonald's Collection 2024",          "B8"),
    "DRI":      (24269, "Destined Rivals",                     "B8"),
    "BLK":      (24325, "Black Bolt",                          "B8"),
    "WHT":      (24326, "White Flare",                         "B8"),
    "SVE":      (24382, "Scarlet & Violet Energies",           "B8"),
    # Mega Evolution Era (B9)
    "MEG":      (24380, "Mega Evolution",                      "B9"),
    "PFL":      (24448, "Phantasmal Flames",                   "B9"),
    "MEP":      (24451, "Mega Evolution Promos",               "B9"),
    "MEE":      (24461, "Mega Evolution Energies",             "B9"),
    "ASC":      (24541, "Ascended Heroes",                     "B9"),
    "POR":      (24587, "Perfect Order",                       "B9"),
    "CRI":      (24655, "Chaos Rising",                        "B9"),
}

pattern_re = re.compile(r'\(([^)]+)\)$')

def get_rate():
    for url in RATE_APIS:
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            rates = data.get("rates") or data.get("conversion_rates", {})
            if "ZAR" in rates:
                return Decimal(str(rates["ZAR"]))
        except Exception:
            continue
    print("WARNING: Could not fetch live rate, using R18.50")
    return Decimal("18.50")

def round_up_50c(zar):
    val = max(MIN_ZAR, Decimal(str(zar)))
    return Decimal(math.ceil(float(val) * 2)) / 2

def clean_name(name):
    name = re.sub(r'\([^)]+\)', '', name).strip()
    return re.sub(r'[^a-zA-Z0-9\s]', '', name).strip()

def extract_pattern(name):
    match = pattern_re.search(name.strip())
    if match:
        return match.group(1).strip()
    return ''

def get_db_variant(subtype, pattern):
    if pattern and pattern in PATTERN_TO_VARIANT:
        variant = PATTERN_TO_VARIANT[pattern]
        if variant is not None:
            return variant
    return SUBTYPE_TO_VARIANT.get(subtype, 'N')

def fetch_group(group_id, set_code, set_name, era_code, rate, writer, total_rows):
    era_name = ERA_NAMES.get(era_code, era_code)

    # Fetch products
    try:
        r = requests.get(f"{TCGCSV_BASE}/{group_id}/products", headers=HEADERS, timeout=30)
        r.raise_for_status()
        products = r.json().get("results", [])
    except Exception as e:
        print(f"  ERROR fetching products: {e}")
        return 0

    # Fetch prices
    prices = {}
    try:
        r = requests.get(f"{TCGCSV_BASE}/{group_id}/prices", headers=HEADERS, timeout=30)
        r.raise_for_status()
        for row in r.json().get("results", []):
            pid = row.get("productId")
            sub = row.get("subTypeName", "")
            prices[(pid, sub)] = row
    except Exception as e:
        print(f"  ERROR fetching prices: {e}")

    rows_written = 0
    for p in products:
        pid = p.get("productId")
        name = (p.get("name") or "").strip()
        image_url = p.get("imageUrl", "")
        ext = p.get("extendedData", [])

        # Extract extended data fields
        def _ext(field):
            for item in ext:
                if item.get("name") == field:
                    return item.get("value", "")
            return ""

        number = _ext("Number")
        rarity = _ext("Rarity")
        card_type = _ext("CardType") or _ext("cardType")
        hp = _ext("HP") or _ext("hp")
        stage = _ext("Stage") or _ext("stage")
        artist = _ext("Artist") or _ext("artist")
        is_card = bool(number and rarity)

        # Extract name pattern
        name_pattern = extract_pattern(name)
        base_clean = clean_name(name)

        # Get all price rows for this product
        product_prices = {sub: data for (p_id, sub), data in prices.items() if p_id == pid}
        if not product_prices:
            product_prices = {"": None}

        for sub, price_data in product_prices.items():
            market_usd = None
            low_usd = None
            mid_usd = None
            high_usd = None
            direct_low_usd = None
            pokebulk_zar = None

            if price_data:
                market_usd = price_data.get("marketPrice")
                low_usd    = price_data.get("lowPrice")
                mid_usd    = price_data.get("midPrice")
                high_usd   = price_data.get("highPrice")
                direct_low_usd = price_data.get("directLowPrice")

                if market_usd and float(market_usd) > 0:
                    pokebulk_zar = float(round_up_50c(Decimal(str(market_usd)) * rate * MARKUP))

            db_variant = get_db_variant(sub, name_pattern)
            tcgplayer_url = f"https://www.tcgplayer.com/product/{pid}" if pid else ""

            writer.writerow({
                'era':            era_name,
                'set_name':       set_name,
                'abbreviation':   set_code,
                'group_id':       group_id,
                'productId':      pid,
                'name':           name,
                'cleanName':      base_clean,
                'number':         number,
                'rarity':         rarity,
                'cardType':       card_type,
                'hp':             hp,
                'stage':          stage,
                'artist':         artist,
                'isCard':         'TRUE' if is_card else 'FALSE',
                'subTypeName':    sub,
                'market_usd':     market_usd or '',
                'low_usd':        low_usd or '',
                'mid_usd':        mid_usd or '',
                'high_usd':       high_usd or '',
                'direct_low_usd': direct_low_usd or '',
                'usd_zar_rate':   float(rate),
                'pokebulk_zar':   pokebulk_zar or '',
                'tcgplayer_url':  tcgplayer_url,
                'name_pattern':   name_pattern,
                'db_variant':     db_variant,
            })
            rows_written += 1

    return rows_written


def main():
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"pokebulk_cards_{date_str}.csv"

    print("PokéBulk SA — Bible CSV Generator")
    print("="*50)

    # Get exchange rate
    print("Fetching USD/ZAR rate...")
    rate = get_rate()
    print(f"  1 USD = R{rate}")

    total_sets = len(GROUP_CONFIG)
    total_rows = 0

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        for i, (code, (gid, sname, era_code)) in enumerate(GROUP_CONFIG.items(), 1):
            print(f"[{i:>3}/{total_sets}] {code:<12} {sname[:40]}", end=' ... ', flush=True)
            rows = fetch_group(gid, code, sname, era_code, rate, writer, total_rows)
            total_rows += rows
            print(f"{rows} rows")
            time.sleep(0.2)

    print("="*50)
    print(f"DONE — {total_rows:,} rows written to {filename}")
    print(f"Sets processed: {total_sets}")


if __name__ == "__main__":
    main()
