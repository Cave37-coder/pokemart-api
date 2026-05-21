"""
rebuild_from_tcgcsv.py
======================
PokéBulk SA — TCGCSV Master Rebuild

WHAT THIS DOES:
  Reads tcgcsv_all_products.json (fetched locally by fetch_tcgcsv.py)

  For every TCGCSV card product in every group:
    - Normalizes card number (018/172 → 18)
    - Finds ALL existing DB records for that set + card_number
    - Stamps tcgcsv_product_id on every matching record
    - If zero DB records exist → creates one new record (inactive, price=0)

  Never touches: price, image_url, attacks, name_japanese, hp, abilities,
                 variant_override (preserves V, VX, BRH-PB etc.)
  Never deletes anything.

USAGE:
  python manage.py rebuild_from_tcgcsv                        # all groups
  python manage.py rebuild_from_tcgcsv --gid 2948            # BRS only
  python manage.py rebuild_from_tcgcsv --gid 2948 --dry-run  # test first
"""

import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from products.models import PokemonProduct, CardSet, Era, Category

# ---------------------------------------------------------------------------
RARITY_MAP = {
    "Common":                    "common",
    "Uncommon":                  "uncommon",
    "Rare":                      "rare",
    "Rare Holo":                 "holo_rare",
    "Rare Holo V":               "holo_rare",
    "Rare Holo VMAX":            "ultra_rare",
    "Rare Holo VSTAR":           "ultra_rare",
    "Rare Holo EX":              "ultra_rare",
    "Rare Holo GX":              "ultra_rare",
    "Ultra Rare":                "ultra_rare",
    "Double Rare":               "ultra_rare",
    "Illustration Rare":         "illustration_rare",
    "Special Illustration Rare": "special_illustration_rare",
    "Hyper Rare":                "hyper_rare",
    "Mega Hyper Rare":           "mega_hyper_rare",
    "Mega Attack Rare":          "mega_attack_rare",
    "ACE SPEC Rare":             "ace_spec",
    "Trainer Gallery Rare Holo": "ultra_rare",
    "Shiny Rare":                "secret_rare",
    "Shiny Ultra Rare":          "secret_rare",
    "Radiant Rare":              "holo_rare",
    "Amazing Rare":              "holo_rare",
    "Promo":                     "promo",
    "Rare Secret":               "secret_rare",
    "Rare Rainbow":              "hyper_rare",
    "Rare Shiny":                "secret_rare",
    "Rare Shiny GX":             "secret_rare",
}

ERA_META = {
    "B1": ("WotC Base Era",        1),
    "B2": ("EX Era",               2),
    "B3": ("Diamond & Pearl Era",  3),
    "B4": ("Black & White Era",    4),
    "B5": ("XY Era",               5),
    "B6": ("Sun & Moon Era",       6),
    "B7": ("Sword & Shield Era",   7),
    "B8": ("Scarlet & Violet Era", 8),
    "B9": ("Mega Evolution Era",   9),
    "SP": ("Special & Promos",    10),
}

GROUP_CONFIG = {
    # ── WotC / Original (B1) ─────────────────────────────────────────────
    604:   ("BS",      "B1", "Base Set",                           "1999-01-09"),
    1663:  ("BSS",     "B1", "Base Set Shadowless",                "1998-12-01"),
    635:   ("JU",      "B1", "Jungle",                             "1999-06-16"),
    630:   ("FO",      "B1", "Fossil",                             "1999-10-10"),
    605:   ("B2",      "B1", "Base Set 2",                         "2000-02-24"),
    1373:  ("TR",      "B1", "Team Rocket",                        "2000-04-24"),
    1441:  ("G1",      "B1", "Gym Heroes",                         "2000-08-14"),
    1440:  ("G2",      "B1", "Gym Challenge",                      "2000-10-16"),
    1396:  ("N1",      "B1", "Neo Genesis",                        "2000-12-16"),
    1434:  ("N2",      "B1", "Neo Discovery",                      "2001-06-01"),
    1389:  ("N3",      "B1", "Neo Revelation",                     "2001-09-21"),
    1444:  ("N4",      "B1", "Neo Destiny",                        "2002-02-28"),
    1374:  ("LC",      "B1", "Legendary Collection",               "2002-05-24"),
    648:   ("SI1",     "B1", "Southern Islands",                   "2001-07-31"),
    1418:  ("PR-WB",   "B1", "Wizards Black Star Promos",          "1999-01-09"),
    1423:  ("PR-NB",   "B1", "Nintendo Black Star Promos",         "2003-07-01"),
    1375:  ("EXP",     "B1", "Expedition Base Set",                "2002-09-15"),
    1397:  ("AQ",      "B1", "Aquapolis",                          "2003-01-15"),
    1372:  ("SK",      "B1", "Skyridge",                           "2003-05-12"),
    # ── EX Era (B2) ──────────────────────────────────────────────────────
    1393:  ("RS",      "B2", "Ruby & Sapphire",                    "2003-07-18"),
    1392:  ("SS",      "B2", "Sandstorm",                          "2003-09-18"),
    1376:  ("DR",      "B2", "Dragon",                             "2003-11-24"),
    1377:  ("MA",      "B2", "Team Magma vs Team Aqua",            "2004-03-15"),
    1416:  ("HL",      "B2", "Hidden Legends",                     "2004-06-14"),
    1419:  ("RG",      "B2", "FireRed & LeafGreen",                "2004-08-30"),
    1428:  ("TRR",     "B2", "Team Rocket Returns",                "2004-11-08"),
    1404:  ("DX",      "B2", "Deoxys",                             "2005-02-14"),
    1410:  ("EM",      "B2", "Emerald",                            "2005-05-09"),
    1398:  ("UF",      "B2", "Unseen Forces",                      "2005-08-22"),
    1429:  ("DS",      "B2", "Delta Species",                      "2005-10-31"),
    1378:  ("LM",      "B2", "Legend Maker",                       "2006-02-08"),
    1379:  ("HP",      "B2", "Holon Phantoms",                     "2006-05-03"),
    1395:  ("CG",      "B2", "Crystal Guardians",                  "2006-08-30"),
    1411:  ("DF",      "B2", "Dragon Frontiers",                   "2006-11-08"),
    1383:  ("PK",      "B2", "Power Keepers",                      "2007-02-14"),
    1422:  ("POP1",    "B2", "POP Series 1",                       "2004-07-01"),
    1447:  ("POP2",    "B2", "POP Series 2",                       "2005-07-01"),
    1442:  ("POP3",    "B2", "POP Series 3",                       "2006-01-01"),
    1452:  ("POP4",    "B2", "POP Series 4",                       "2006-07-01"),
    1439:  ("POP5",    "B2", "POP Series 5",                       "2007-01-01"),
    1543:  ("TK1",     "B2", "EX Trainer Kit: Latias & Latios",    "2004-01-01"),
    1542:  ("TK2",     "B2", "EX Trainer Kit 2: Plusle & Minun",   "2005-01-01"),
    # ── Diamond & Pearl Era (B3) ─────────────────────────────────────────
    1430:  ("DP",      "B3", "Diamond & Pearl",                    "2007-05-01"),
    1368:  ("MT",      "B3", "Mysterious Treasures",               "2007-08-22"),
    1380:  ("SW",      "B3", "Secret Wonders",                     "2007-11-07"),
    1405:  ("GE",      "B3", "Great Encounters",                   "2008-02-13"),
    1390:  ("MD",      "B3", "Majestic Dawn",                      "2008-05-21"),
    1417:  ("LA",      "B3", "Legends Awakened",                   "2008-08-20"),
    1369:  ("SF",      "B3", "Stormfront",                         "2008-11-05"),
    1406:  ("PL",      "B3", "Platinum",                           "2009-02-11"),
    1367:  ("RR",      "B3", "Rising Rivals",                      "2009-05-16"),
    1384:  ("SV",      "B3", "Supreme Victors",                    "2009-08-19"),
    1391:  ("AR",      "B3", "Arceus",                             "2009-11-04"),
    1421:  ("PR-DPP",  "B3", "Diamond & Pearl Promos",             "2007-05-01"),
    1453:  ("PR-HS",   "B3", "HGSS Black Star Promos",             "2010-02-10"),
    1432:  ("POP6",    "B3", "POP Series 6",                       "2007-07-01"),
    1414:  ("POP7",    "B3", "POP Series 7",                       "2008-01-01"),
    1450:  ("POP8",    "B3", "POP Series 8",                       "2008-07-01"),
    1446:  ("POP9",    "B3", "POP Series 9",                       "2009-01-01"),
    1402:  ("HS",      "B3", "HeartGold & SoulSilver",             "2010-02-10"),
    1399:  ("UL",      "B3", "Unleashed",                          "2010-05-12"),
    1403:  ("UD",      "B3", "Undaunted",                          "2010-08-18"),
    1381:  ("TM",      "B3", "Triumphant",                         "2010-11-03"),
    1415:  ("CL",      "B3", "Call of Legends",                    "2011-02-09"),
    1541:  ("TK-DP",   "B3", "DP Trainer Kit: Manaphy & Lucario",  "2007-01-01"),
    1540:  ("TK-HS",   "B3", "HGSS Trainer Kit: Gyarados & Raichu","2010-01-01"),
    1433:  ("RUM",     "B3", "Rumble",                             "2009-11-01"),
    # ── Black & White Era (B4) ───────────────────────────────────────────
    1407:  ("PR-BLW",  "B4", "BW Black Star Promos",               "2011-04-06"),
    1400:  ("BLW",     "B4", "Black & White",                      "2011-04-25"),
    1424:  ("EPO",     "B4", "Emerging Powers",                    "2011-08-31"),
    1385:  ("NVI",     "B4", "Noble Victories",                    "2011-11-16"),
    1412:  ("NXD",     "B4", "Next Destinies",                     "2012-02-08"),
    1386:  ("DEX",     "B4", "Dark Explorers",                     "2012-05-09"),
    1394:  ("DRX",     "B4", "Dragons Exalted",                    "2012-08-15"),
    1426:  ("DRV",     "B4", "Dragon Vault",                       "2012-10-05"),
    1408:  ("BCR",     "B4", "Boundaries Crossed",                 "2012-11-07"),
    1413:  ("PLS",     "B4", "Plasma Storm",                       "2013-02-06"),
    1382:  ("PLF",     "B4", "Plasma Freeze",                      "2013-05-08"),
    1370:  ("PLB",     "B4", "Plasma Blast",                       "2013-08-14"),
    1409:  ("LTR",     "B4", "Legendary Treasures",                "2013-11-06"),
    1465:  ("LTRRC",   "B4", "Legendary Treasures: Radiant Collection","2013-11-06"),
    1401:  ("MCD11",   "B4", "McDonalds 2011",                     "2011-07-01"),
    1427:  ("MCD12",   "B4", "McDonalds 2012",                     "2012-07-01"),
    1538:  ("TK-BLW",  "B4", "BW Trainer Kit: Excadrill & Zoroark","2012-01-01"),
    # ── XY Era (B5) ──────────────────────────────────────────────────────
    1451:  ("PR-XY",   "B5", "XY Black Star Promos",               "2014-01-08"),
    1387:  ("XY",      "B5", "XY",                                 "2014-02-05"),
    1464:  ("FLF",     "B5", "Flashfire",                          "2014-05-07"),
    1481:  ("FFI",     "B5", "Furious Fists",                      "2014-08-13"),
    1494:  ("PHF",     "B5", "Phantom Forces",                     "2014-11-05"),
    1509:  ("PRC",     "B5", "Primal Clash",                       "2015-02-04"),
    1525:  ("DCR",     "B5", "Double Crisis",                      "2015-03-25"),
    1534:  ("ROS",     "B5", "Roaring Skies",                      "2015-05-06"),
    1576:  ("AOR",     "B5", "Ancient Origins",                    "2015-08-19"),
    1661:  ("BKT",     "B5", "BREAKthrough",                       "2015-11-04"),
    1701:  ("BKP",     "B5", "BREAKpoint",                         "2016-02-03"),
    1728:  ("GEN",     "B5", "Generations",                        "2016-02-22"),
    1729:  ("GENRC",   "B5", "Generations: Radiant Collection",    "2016-02-22"),
    1780:  ("FCO",     "B5", "Fates Collide",                      "2016-05-02"),
    1815:  ("STS",     "B5", "Steam Siege",                        "2016-08-03"),
    1842:  ("EVO",     "B5", "Evolutions",                         "2016-11-02"),
    1522:  ("KSS",     "B5", "Kalos Starter Set",                  "2013-11-08"),
    1692:  ("MCD14",   "B5", "McDonalds 2014",                     "2014-07-01"),
    1694:  ("MCD15",   "B5", "McDonalds 2015",                     "2015-07-01"),
    3087:  ("MCD16",   "B5", "McDonalds 2016",                     "2016-07-01"),
    1532:  ("TK-SN",   "B5", "XY Trainer Kit: Sylveon & Noivern",  "2014-08-13"),
    1533:  ("TK-BW2",  "B5", "XY Trainer Kit: Bisharp & Wigglytuff","2015-02-04"),
    1536:  ("TK-LL",   "B5", "XY Trainer Kit: Latias & Latios",    "2015-08-19"),
    1796:  ("TK-PS",   "B5", "XY Trainer Kit: Pikachu Libre & Suicune","2016-02-03"),
    # ── Sun & Moon Era (B6) ──────────────────────────────────────────────
    1861:  ("PR-SM",   "B6", "SM Black Star Promos",               "2017-01-06"),
    1863:  ("SUM",     "B6", "Sun & Moon",                         "2017-02-03"),
    1919:  ("GRI",     "B6", "Guardians Rising",                   "2017-05-05"),
    1957:  ("BUS",     "B6", "Burning Shadows",                    "2017-08-04"),
    2054:  ("SLG",     "B6", "Shining Legends",                    "2017-10-06"),
    2071:  ("CIN",     "B6", "Crimson Invasion",                   "2017-11-03"),
    2178:  ("UPR",     "B6", "Ultra Prism",                        "2018-02-02"),
    2209:  ("FLI",     "B6", "Forbidden Light",                    "2018-05-04"),
    2278:  ("CES",     "B6", "Celestial Storm",                    "2018-08-03"),
    2295:  ("DRM",     "B6", "Dragon Majesty",                     "2018-09-07"),
    2328:  ("LOT",     "B6", "Lost Thunder",                       "2018-11-02"),
    2377:  ("TEU",     "B6", "Team Up",                            "2019-02-01"),
    2409:  ("DET",     "B6", "Detective Pikachu",                  "2019-05-03"),
    2420:  ("UNB",     "B6", "Unbroken Bonds",                     "2019-05-03"),
    2464:  ("UNM",     "B6", "Unified Minds",                      "2019-08-02"),
    2480:  ("HIF",     "B6", "Hidden Fates",                       "2019-08-23"),
    2594:  ("HIFSV",   "B6", "Hidden Fates: Shiny Vault",          "2019-08-23"),
    2534:  ("CEC",     "B6", "Cosmic Eclipse",                     "2019-11-01"),
    2148:  ("MCD17",   "B6", "McDonalds 2017",                     "2017-07-01"),
    2364:  ("MCD18",   "B6", "McDonalds 2018",                     "2018-07-01"),
    2555:  ("MCD19",   "B6", "McDonalds 2019",                     "2019-07-01"),
    2069:  ("SMK1",    "B6", "SM Trainer Kit: Lycanroc & Alolan Raichu","2017-05-05"),
    2208:  ("SMK2",    "B6", "SM Trainer Kit: Alolan Sandslash & Alolan Ninetales","2018-02-02"),
    # ── Sword & Shield Era (B7) ──────────────────────────────────────────
    2545:  ("PR-SW",   "B7", "SWSH Black Star Promos",             "2020-01-03"),
    2585:  ("SSH",     "B7", "Sword & Shield",                     "2020-02-07"),
    2626:  ("RCL",     "B7", "Rebel Clash",                        "2020-05-01"),
    2675:  ("DAA",     "B7", "Darkness Ablaze",                    "2020-08-14"),
    2685:  ("CPA",     "B7", "Champion's Path",                    "2020-09-25"),
    2701:  ("VIV",     "B7", "Vivid Voltage",                      "2020-11-13"),
    2754:  ("SHF",     "B7", "Shining Fates",                      "2021-02-19"),
    2781:  ("SHFSV",   "B7", "Shining Fates: Shiny Vault",         "2021-02-19"),
    2765:  ("BST",     "B7", "Battle Styles",                      "2021-03-19"),
    2807:  ("CRE",     "B7", "Chilling Reign",                     "2021-06-18"),
    2848:  ("EVS",     "B7", "Evolving Skies",                     "2021-08-27"),
    2867:  ("CEL",     "B7", "Celebrations",                       "2021-10-08"),
    2931:  ("CELCC",   "B7", "Celebrations: Classic Collection",   "2021-10-08"),
    2906:  ("FST",     "B7", "Fusion Strike",                      "2021-11-12"),
    2948:  ("BRS",     "B7", "Brilliant Stars",                    "2022-02-25"),
    3020:  ("BRSTG",   "B7", "Brilliant Stars Trainer Gallery",    "2022-02-25"),
    3040:  ("ASR",     "B7", "Astral Radiance",                    "2022-05-27"),
    3068:  ("ASRTG",   "B7", "Astral Radiance Trainer Gallery",    "2022-05-27"),
    3064:  ("PGO",     "B7", "Pokemon GO",                         "2022-07-01"),
    3118:  ("LOR",     "B7", "Lost Origin",                        "2022-09-09"),
    3172:  ("LORTG",   "B7", "Lost Origin Trainer Gallery",        "2022-09-09"),
    3170:  ("SIT",     "B7", "Silver Tempest",                     "2022-11-11"),
    17674: ("SITTG",   "B7", "Silver Tempest Trainer Gallery",     "2022-11-11"),
    17688: ("CRZ",     "B7", "Crown Zenith",                       "2023-01-20"),
    17689: ("CRZGG",   "B7", "Crown Zenith: Galarian Gallery",     "2023-01-20"),
    2782:  ("MCD21",   "B7", "McDonalds 25th Anniversary",         "2021-06-11"),
    3150:  ("MCD22",   "B7", "McDonalds 2022",                     "2022-08-01"),
    3179:  ("TTBB",    "B7", "Trick or Trade 2022",                "2022-10-01"),
    22880: ("PRIZEPACK","B7","Prize Pack Series",                  "2022-09-01"),
    2776:  ("FPP",     "B7", "First Partner Pack",                 "2021-11-12"),
    2686:  ("BTA",     "B7", "Battle Academy",                     "2020-03-06"),
    3051:  ("BA22",    "B7", "Battle Academy 2022",                "2022-03-25"),
    # ── Scarlet & Violet Era (B8) ─────────────────────────────────────────
    22872: ("SVP",     "B8", "Scarlet & Violet Promos",            "2023-01-01"),
    22873: ("SV1",     "B8", "Scarlet & Violet",                   "2023-03-31"),
    23120: ("SV2",     "B8", "Paldea Evolved",                     "2023-06-09"),
    23228: ("SV3",     "B8", "Obsidian Flames",                    "2023-08-11"),
    23237: ("MEW",     "B8", "Scarlet & Violet 151",               "2023-09-22"),
    23286: ("SV4",     "B8", "Paradox Rift",                       "2023-11-03"),
    23353: ("SV4PT5",  "B8", "Paldean Fates",                      "2024-01-26"),
    23381: ("TEF",     "B8", "Temporal Forces",                    "2024-03-22"),
    23473: ("TWM",     "B8", "Twilight Masquerade",                "2024-05-24"),
    23529: ("SFA",     "B8", "Shrouded Fable",                     "2024-08-02"),
    23537: ("SCR",     "B8", "Stellar Crown",                      "2024-09-13"),
    23651: ("SSP",     "B8", "Surging Sparks",                     "2024-11-08"),
    23821: ("PRE",     "B8", "Prismatic Evolutions",               "2025-01-17"),
    24073: ("JTG",     "B8", "Journey Together",                   "2025-03-28"),
    24269: ("DRI",     "B8", "Destined Rivals",                    "2025-05-30"),
    24325: ("BLK",     "B8", "Black Bolt",                         "2025-07-18"),
    24326: ("WHT",     "B8", "White Flare",                        "2025-09-19"),
    24382: ("SVE",     "B8", "Scarlet & Violet Energies",          "2023-03-31"),
    23306: ("MCD23",   "B8", "McDonalds 2023",                     "2023-07-01"),
    24163: ("MCD24",   "B8", "McDonalds 2024",                     "2024-07-01"),
    23323: ("TCGCL",   "B8", "Trading Card Game Classic",          "2023-10-01"),
    23266: ("TTBB23",  "B8", "Trick or Trade 2023",                "2023-10-01"),
    23561: ("TTBB24",  "B8", "Trick or Trade 2024",                "2024-10-01"),
    23520: ("BA24",    "B8", "Battle Academy 2024",                "2024-03-22"),
    # ── Mega Evolution Era (B9) ───────────────────────────────────────────
    24380: ("MEG",     "B9", "Mega Evolution",                     "2024-05-01"),
    24448: ("PFL",     "B9", "Phantasmal Flames",                  "2024-08-01"),
    24541: ("ASC",     "B9", "Ascended Heroes",                    "2024-11-01"),
    24587: ("POR",     "B9", "Perfect Order",                      "2025-02-01"),
    24451: ("MEP",     "B9", "Mega Evolution Promos",              "2024-05-01"),
    24461: ("MEE",     "B9", "Mega Evolution Energies",            "2024-05-01"),
    24655: ("CRI",     "B9", "Chaos Rising",                       "2026-05-22"),
    24688: ("ME05",    "B9", "Pitch Black",                        "2026-07-01"),
    # ── Special & Promos (SP) ────────────────────────────────────────────
    1455:  ("PR-BEST", "SP", "Best of Game Promos",                "2003-01-01"),
    2155:  ("CCP",     "SP", "Countdown Calendar Promos",          "2017-12-01"),
    2205:  ("PWCP",    "SP", "Pikachu World Collection Promos",    "2010-01-01"),
    2214:  ("KWBP",    "SP", "Kids WB Promos",                     "2000-01-01"),
    2282:  ("WCD",     "SP", "World Championship Decks",           "2004-01-01"),
    2289:  ("BLE",     "SP", "Blister Exclusives",                 "2017-01-01"),
    2332:  ("PPP",     "SP", "Professor Program Promos",           "2018-01-01"),
    2374:  ("MCAP",    "SP", "Miscellaneous Cards & Products",     "2017-01-01"),
    1528:  ("JUMBO",   "SP", "Jumbo Cards",                        "2003-01-01"),
    1539:  ("LEAGUE",  "SP", "League & Championship Cards",        "2004-01-01"),
    1938:  ("ALTART",  "SP", "Alternate Art Promos",               "2017-01-01"),
    1853:  ("BSTEX",   "SP", "EX Battle Stadium",                  "2016-01-01"),
    2175:  ("BKP-BK",  "SP", "Burger King Promos",                 "2000-01-01"),
    24493: ("SAMPLE",  "SP", "e-Reader Sample Cards",              "2002-01-01"),
}

def norm_number(raw):
    """018/172 → 18,  TG01/TG30 → TG01,  SWSH001 → SWSH001"""
    if not raw:
        return ""
    part = str(raw).split("/")[0].strip()
    # If purely numeric, strip leading zeros
    if part.isdigit():
        return str(int(part))
    return part

def get_or_create_era(era_code):
    name, _sort = ERA_META.get(era_code, (f"Era {era_code}", 99))
    era, _ = Era.objects.get_or_create(
        code=era_code,
        defaults={"name": name},
    )
    return era

def get_or_create_set(db_code, era_code, set_name, release_date):
    era = get_or_create_era(era_code)
    card_set, created = CardSet.objects.get_or_create(
        code=db_code,
        defaults={"name": set_name, "era": era, "release_date": release_date},
    )
    if not created and card_set.era_id != era.pk:
        card_set.era = era
        card_set.save(update_fields=["era"])
    return card_set, created


class Command(BaseCommand):
    help = (
        "Rebuild card DB from local tcgcsv_all_products.json. "
        "Matches by card_number, stamps tcgcsv_product_id on ALL variants. "
        "Creates new records for cards not in DB. Never touches price/images/attacks."
    )

    def add_arguments(self, parser):
        parser.add_argument("--gid", type=int, default=None,
            help="Process only this groupId (e.g. 2948 for BRS)")
        parser.add_argument("--dry-run", action="store_true", default=False,
            help="Show counts, no DB writes")
        parser.add_argument("--data-file", default="tcgcsv_all_products.json",
            help="Path to tcgcsv_all_products.json")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        gid_filter = options["gid"]
        data_file = options["data_file"]

        if not os.path.exists(data_file):
            raise CommandError(
                f"Data file not found: {data_file}\n"
                f"Run fetch_tcgcsv.py first."
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes\n"))

        self.stdout.write(f"Loading {data_file}...")
        with open(data_file, encoding="utf-8") as f:
            tcgcsv_data = json.load(f)
        self.stdout.write(f"  {len(tcgcsv_data)} groups in file\n")

        category, _ = Category.objects.get_or_create(
            slug="cards", defaults={"name": "Cards"}
        )

        # Build work list — only configured groups
        if gid_filter:
            if gid_filter not in GROUP_CONFIG:
                raise CommandError(f"groupId {gid_filter} not in GROUP_CONFIG")
            if str(gid_filter) not in tcgcsv_data:
                raise CommandError(f"groupId {gid_filter} not in data file")
            work = [(gid_filter, GROUP_CONFIG[gid_filter], tcgcsv_data[str(gid_filter)])]
        else:
            work = []
            for gid, cfg in sorted(GROUP_CONFIG.items()):
                gid_str = str(gid)
                if gid_str in tcgcsv_data:
                    work.append((gid, cfg, tcgcsv_data[gid_str]))

        self.stdout.write(f"Processing {len(work)} groups...\n")

        total_sets_created = 0
        total_stamped = 0
        total_created = 0
        total_skipped = 0

        for i, (gid, cfg, data) in enumerate(work, 1):
            db_code, era_code, set_name, release_date = cfg
            cards = data.get("cards", [])
            if not cards:
                continue

            # Ensure CardSet exists
            card_set, set_created = get_or_create_set(
                db_code, era_code, set_name, release_date
            )
            if set_created:
                total_sets_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✚ New set: {db_code} — {set_name}")
                )

            self.stdout.write(
                f"[{i}/{len(work)}] {db_code:12} {set_name:45} {len(cards):4} TCGCSV cards"
            )

            # Load ALL existing DB records for this set
            # Key: normalized card_number → list of PokemonProduct
            db_by_number: dict[str, list] = {}
            db_by_tcgid: dict[int, object] = {}
            for p in PokemonProduct.objects.filter(card_set=card_set):
                num = norm_number(str(p.card_number or ""))
                db_by_number.setdefault(num, []).append(p)
                if p.tcgcsv_product_id:
                    db_by_tcgid[p.tcgcsv_product_id] = p

            to_update = []
            to_create = []
            stamped = created = skipped = 0

            for card in cards:
                pid = card.get("productId")
                if pid is None:
                    continue
                pid = int(pid)

                tcg_name = (card.get("name") or "").strip()
                raw_number = card.get("_number", "")
                rarity_raw = card.get("_rarity", "")
                rarity = RARITY_MAP.get(rarity_raw, "common")
                norm_num = norm_number(raw_number)

                # ── Match: tcgcsv_product_id first (already stamped) ────
                if pid in db_by_tcgid:
                    skipped += 1
                    continue

                # ── Match: card_number → stamp ALL variants of this card ─
                # For numeric numbers, match as int string
                # For alphanumeric (TG01, RT6), match as 0 (won't match — will create)
                matches = db_by_number.get(norm_num, [])
                if matches:
                    changed_any = False
                    for p in matches:
                        if p.tcgcsv_product_id != pid:
                            p.tcgcsv_product_id = pid
                            to_update.append(p)
                            changed_any = True
                    if changed_any:
                        stamped += 1
                    else:
                        skipped += 1
                else:
                    # ── No match → create new record ────────────────────
                    # card_number is IntegerField — use int if numeric, else 0
                    # Store the raw alphanumeric number in pb_id for reference
                    if norm_num.isdigit():
                        card_num_int = int(norm_num)
                        num_padded = norm_num.zfill(3)
                    else:
                        card_num_int = 0
                        num_padded = norm_num  # e.g. TG01, RT6, SWSH001

                    pb_id = f"PB-{db_code}-N-{num_padded}"
                    to_create.append(PokemonProduct(
                        pb_id=pb_id,
                        name=tcg_name,
                        card_set=card_set,
                        category=category,
                        rarity=rarity,
                        card_number=card_num_int,
                        variant_override="N",
                        tcgcsv_product_id=pid,
                        price=0,
                        stock=0,
                        is_active=False,
                    ))
                    created += 1

            if not dry_run:
                if to_update:
                    with transaction.atomic():
                        PokemonProduct.objects.bulk_update(
                            to_update, ["tcgcsv_product_id"]
                        )
                if to_create:
                    PokemonProduct.objects.bulk_create(
                        to_create, ignore_conflicts=True
                    )

            total_stamped += stamped
            total_created += created
            total_skipped += skipped

            self.stdout.write(self.style.SUCCESS(
                f"  → stamped={stamped}  created={created}  skipped={skipped}"
            ))

        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"DONE\n"
            f"  New sets created:          {total_sets_created}\n"
            f"  Cards stamped (tcgcsv_id): {total_stamped}\n"
            f"  New cards created:         {total_created}\n"
            f"  Already correct (skipped): {total_skipped}\n"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — nothing written to DB"))
