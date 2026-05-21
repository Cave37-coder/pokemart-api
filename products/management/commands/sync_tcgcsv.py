"""
management/commands/sync_tcgcsv.py
====================================
PokéBulk SA — TCGCSV master sync command

WHAT THIS DOES
--------------
• Fetches all configured groups from tcgcsv.com
• For each group → fetches products (cards only, filtered by 'Number' in extendedData)
• For each group → fetches prices
• One DB record per TCGCSV product row  (one record = one variant of one card)
• Creates missing Era / CardSet records automatically from GROUP_CONFIG
• Nightly price updates by tcgcsv_product_id — no name matching ever

USAGE
-----
  python manage.py sync_tcgcsv                         # full run
  python manage.py sync_tcgcsv --set-code BRS          # single set
  python manage.py sync_tcgcsv --set-code BRS --dry-run
  python manage.py sync_tcgcsv --rate 19.50            # override USD/ZAR rate
  python manage.py sync_tcgcsv --delay 0.5             # throttle (seconds between groups)

SUBTYPE → VARIANT RULES
------------------------
  Normal               → N
  Holofoil             → H
  Reverse Holofoil     → RH
  1st Edition Normal   → N
  1st Edition Holofoil → H
  Unlimited Normal     → N
  Unlimited Holofoil   → H
  "" (empty)           → H   ← TG / GG / Prize Pack sets (single-variant Holo only)

PRICE FORMULA
-------------
  ZAR = USD × rate × 1.10  rounded UP to nearest R0.50
"""

import math
import time
import requests
from decimal import Decimal, ROUND_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import PokemonProduct, CardSet, Era, Category

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")

# Rate fallback APIs (tried in order)
RATE_APIS = [
    "https://api.exchangerate-api.com/v4/latest/USD",
    "https://open.er-api.com/v6/latest/USD",
]

# ---------------------------------------------------------------------------
# Subtype → variant code
# ---------------------------------------------------------------------------

SUBTYPE_MAP: dict[str, str] = {
    "Normal":               "N",
    "Holofoil":             "H",
    "Reverse Holofoil":     "RH",
    "1st Edition Normal":   "N",
    "1st Edition Holofoil": "H",
    "Unlimited Normal":     "N",
    "Unlimited Holofoil":   "H",
    "":                     "H",   # TG / GG / Prize Pack — single variant, always Holo
}

# ---------------------------------------------------------------------------
# Rarity → DB rarity slug
# ---------------------------------------------------------------------------

RARITY_MAP: dict[str, str] = {
    "Common":                        "common",
    "Uncommon":                      "uncommon",
    "Rare":                          "rare",
    "Rare Holo":                     "holo_rare",
    "Rare Holo V":                   "holo_rare",
    "Rare Holo VMAX":                "ultra_rare",
    "Rare Holo VSTAR":               "ultra_rare",
    "Rare Holo EX":                  "ultra_rare",
    "Rare Holo GX":                  "ultra_rare",
    "Ultra Rare":                    "ultra_rare",
    "Double Rare":                   "ultra_rare",
    "Illustration Rare":             "illustration_rare",
    "Special Illustration Rare":     "special_illustration_rare",
    "Hyper Rare":                    "hyper_rare",
    "Mega Hyper Rare":               "mega_hyper_rare",
    "Mega Attack Rare":              "mega_attack_rare",
    "ACE SPEC Rare":                 "ace_spec",
    "Trainer Gallery Rare Holo":     "ultra_rare",
    "Shiny Rare":                    "secret_rare",
    "Shiny Ultra Rare":              "secret_rare",
    "Radiant Rare":                  "holo_rare",
    "Amazing Rare":                  "holo_rare",
    "Promo":                         "promo",
    "Rare Secret":                   "secret_rare",
    "Rare Rainbow":                  "hyper_rare",
    "Rare Shiny":                    "secret_rare",
    "Rare Shiny GX":                 "secret_rare",
}

# ---------------------------------------------------------------------------
# GROUP_CONFIG
# groupId → (db_code, era_code, set_name, release_date)
#
# Special-set flag: sets ending in TG / GG / "Prize Pack" / "Trick or Trade"
# have empty subTypeName on all products → mapped to "H" (single Holo variant).
#
# Full list: ~150 groups across all eras.
# ---------------------------------------------------------------------------

GROUP_CONFIG: dict[int, tuple[str, str, str, str]] = {

    # ── WotC / Original era (B1) ─────────────────────────────────────────
    604:   ("BS",     "B1", "Base Set",                    "1999-01-09"),
    635:   ("JU",     "B1", "Jungle",                      "1999-06-16"),
    630:   ("FO",     "B1", "Fossil",                      "1999-10-10"),
    605:   ("B2",     "B1", "Base Set 2",                  "2000-02-24"),
    1373:  ("TR",     "B1", "Team Rocket",                 "2000-04-24"),
    1420:  ("G1",     "B1", "Gym Heroes",                  "2000-08-14"),
    1421:  ("G2",     "B1", "Gym Challenge",               "2000-10-16"),
    1396:  ("N1",     "B1", "Neo Genesis",                 "2000-12-16"),
    1422:  ("N2",     "B1", "Neo Discovery",               "2001-06-01"),
    1389:  ("N3",     "B1", "Neo Revelation",              "2001-09-21"),
    1424:  ("N4",     "B1", "Neo Destiny",                 "2002-02-28"),
    1374:  ("LC",     "B1", "Legendary Collection",        "2002-05-24"),
    648:   ("SI1",    "B1", "Southern Islands",            "2001-07-31"),
    1418:  ("PR-WB",  "B1", "Wizards Black Star Promos",   "1999-01-09"),
    1423:  ("PR-NB",  "B1", "Nintendo Black Star Promos",  "2003-07-01"),

    # ── e-Card era (B1 — part of WotC broad era for browsing) ────────────
    1375:  ("EX",     "B1", "Expedition Base Set",         "2002-09-15"),
    1397:  ("AQ",     "B1", "Aquapolis",                   "2003-01-15"),
    1372:  ("SK",     "B1", "Skyridge",                    "2003-05-12"),

    # ── EX era (B2) ───────────────────────────────────────────────────────
    1393:  ("RS",     "B2", "Ruby & Sapphire",             "2003-07-18"),
    1392:  ("SS",     "B2", "Sandstorm",                   "2003-09-18"),
    1376:  ("DR",     "B2", "Dragon",                      "2003-11-24"),
    1377:  ("MA",     "B2", "Team Magma vs Team Aqua",     "2004-03-15"),
    1416:  ("HL",     "B2", "Hidden Legends",              "2004-06-14"),
    1419:  ("RG",     "B2", "FireRed & LeafGreen",         "2004-08-30"),
    1425:  ("TRR",    "B2", "Team Rocket Returns",         "2004-11-08"),
    1404:  ("DX",     "B2", "Deoxys",                      "2005-02-14"),
    1410:  ("EM",     "B2", "Emerald",                     "2005-05-09"),
    1398:  ("UF",     "B2", "Unseen Forces",               "2005-08-22"),
    1426:  ("DS",     "B2", "Delta Species",               "2005-10-31"),
    1378:  ("LM",     "B2", "Legend Maker",                "2006-02-08"),
    1379:  ("HP",     "B2", "Holon Phantoms",              "2006-05-03"),
    1395:  ("CG",     "B2", "Crystal Guardians",           "2006-08-30"),
    1411:  ("DF",     "B2", "Dragon Frontiers",            "2006-11-08"),
    1383:  ("PK",     "B2", "Power Keepers",               "2007-02-14"),

    # POP Series (promos — B2 era)
    1427:  ("POP1",   "B2", "POP Series 1",               "2004-07-01"),
    1428:  ("POP2",   "B2", "POP Series 2",               "2005-07-01"),
    1429:  ("POP3",   "B2", "POP Series 3",               "2006-01-01"),
    1430:  ("POP4",   "B2", "POP Series 4",               "2006-07-01"),
    1431:  ("POP5",   "B2", "POP Series 5",               "2007-01-01"),

    # ── Diamond & Pearl era (B3) ──────────────────────────────────────────
    1432:  ("DP",     "B3", "Diamond & Pearl",             "2007-05-01"),
    1433:  ("MT",     "B3", "Mysterious Treasures",        "2007-08-22"),
    1434:  ("SW",     "B3", "Secret Wonders",              "2007-11-07"),
    1405:  ("GE",     "B3", "Great Encounters",            "2008-02-13"),
    1390:  ("MD",     "B3", "Majestic Dawn",               "2008-05-21"),
    1417:  ("LA",     "B3", "Legends Awakened",            "2008-08-20"),
    1369:  ("SF",     "B3", "Stormfront",                  "2008-11-05"),
    1406:  ("PL",     "B3", "Platinum",                    "2009-02-11"),
    1367:  ("RR",     "B3", "Rising Rivals",               "2009-05-16"),
    1384:  ("SV",     "B3", "Supreme Victors",             "2009-08-19"),
    1391:  ("AR",     "B3", "Arceus",                      "2009-11-04"),
    1453:  ("PR-HS",  "B3", "HGSS Black Star Promos",      "2010-02-10"),

    # POP Series 6-9 (DP era)
    1435:  ("POP6",   "B3", "POP Series 6",               "2007-07-01"),
    1414:  ("POP7",   "B3", "POP Series 7",               "2008-01-01"),
    1436:  ("POP8",   "B3", "POP Series 8",               "2008-07-01"),
    1437:  ("POP9",   "B3", "POP Series 9",               "2009-01-01"),

    # HeartGold & SoulSilver (B3 — same browsing era)
    1402:  ("HS",     "B3", "HeartGold & SoulSilver",     "2010-02-10"),
    1399:  ("UL",     "B3", "Unleashed",                  "2010-05-12"),
    1403:  ("UD",     "B3", "Undaunted",                  "2010-08-18"),
    1381:  ("TM",     "B3", "Triumphant",                 "2010-11-03"),
    1415:  ("CL",     "B3", "Call of Legends",            "2011-02-09"),

    # ── Black & White era (B4) ────────────────────────────────────────────
    1407:  ("PR-BLW", "B4", "BW Black Star Promos",       "2011-04-06"),
    1400:  ("BLW",    "B4", "Black & White",              "2011-04-25"),
    1438:  ("EPO",    "B4", "Emerging Powers",            "2011-08-31"),
    1385:  ("NVI",    "B4", "Noble Victories",            "2011-11-16"),
    1412:  ("NXD",    "B4", "Next Destinies",             "2012-02-08"),
    1386:  ("DEX",    "B4", "Dark Explorers",             "2012-05-09"),
    1394:  ("DRX",    "B4", "Dragons Exalted",            "2012-08-15"),
    1439:  ("DRV",    "B4", "Dragon Vault",               "2012-10-05"),
    1408:  ("BCR",    "B4", "Boundaries Crossed",         "2012-11-07"),
    1413:  ("PLS",    "B4", "Plasma Storm",               "2013-02-06"),
    1382:  ("PLF",    "B4", "Plasma Freeze",              "2013-05-08"),
    1370:  ("PLB",    "B4", "Plasma Blast",               "2013-08-14"),
    1409:  ("LTR",    "B4", "Legendary Treasures",        "2013-11-06"),
    1401:  ("MCD11",  "B4", "McDonalds 2011",             "2011-07-01"),
    1440:  ("MCD12",  "B4", "McDonalds 2012",             "2012-07-01"),

    # ── XY era (B5) ───────────────────────────────────────────────────────
    1441:  ("PR-XY",  "B5", "XY Black Star Promos",       "2014-01-08"),
    1387:  ("XY",     "B5", "XY",                         "2014-02-05"),
    1442:  ("FLF",    "B5", "Flashfire",                  "2014-05-07"),
    1443:  ("FFI",    "B5", "Furious Fists",              "2014-08-13"),
    1444:  ("PHF",    "B5", "Phantom Forces",             "2014-11-05"),
    1445:  ("PRC",    "B5", "Primal Clash",               "2015-02-04"),
    1446:  ("DCR",    "B5", "Double Crisis",              "2015-03-25"),
    1447:  ("ROS",    "B5", "Roaring Skies",              "2015-05-06"),
    1448:  ("AOR",    "B5", "Ancient Origins",            "2015-08-19"),
    1449:  ("BKT",    "B5", "BREAKthrough",               "2015-11-04"),
    1450:  ("BKP",    "B5", "BREAKpoint",                 "2016-02-03"),
    1451:  ("GEN",    "B5", "Generations",                "2016-02-22"),
    1452:  ("FCO",    "B5", "Fates Collide",              "2016-05-02"),
    1454:  ("STS",    "B5", "Steam Siege",                "2016-08-03"),
    1455:  ("EVO",    "B5", "Evolutions",                 "2016-11-02"),
    1456:  ("MCD14",  "B5", "McDonalds 2014",             "2014-07-01"),
    1457:  ("MCD15",  "B5", "McDonalds 2015",             "2015-07-01"),
    1458:  ("MCD16",  "B5", "McDonalds 2016",             "2016-07-01"),

    # ── Sun & Moon era (B6) ───────────────────────────────────────────────
    1459:  ("PR-SM",  "B6", "SM Black Star Promos",       "2017-01-06"),
    1460:  ("SUM",    "B6", "Sun & Moon",                 "2017-02-03"),
    1461:  ("GRI",    "B6", "Guardians Rising",           "2017-05-05"),
    1462:  ("BUS",    "B6", "Burning Shadows",            "2017-08-04"),
    1463:  ("SLG",    "B6", "Shining Legends",            "2017-10-06"),
    1464:  ("CIN",    "B6", "Crimson Invasion",           "2017-11-03"),
    1465:  ("UPR",    "B6", "Ultra Prism",                "2018-02-02"),
    1466:  ("FLI",    "B6", "Forbidden Light",            "2018-05-04"),
    1467:  ("CES",    "B6", "Celestial Storm",            "2018-08-03"),
    1468:  ("DRM",    "B6", "Dragon Majesty",             "2018-09-07"),
    1469:  ("LOT",    "B6", "Lost Thunder",               "2018-11-02"),
    2099:  ("TEU",    "B6", "Team Up",                    "2019-02-01"),
    2100:  ("DET",    "B6", "Detective Pikachu",          "2019-05-03"),
    2101:  ("UNB",    "B6", "Unbroken Bonds",             "2019-05-03"),
    2102:  ("UNM",    "B6", "Unified Minds",              "2019-08-02"),
    2110:  ("HIF",    "B6", "Hidden Fates",               "2019-08-23"),
    2111:  ("SMA",    "B6", "Hidden Fates Shiny Vault",   "2019-08-23"),
    2103:  ("CEC",    "B6", "Cosmic Eclipse",             "2019-11-01"),
    1470:  ("MCD17",  "B6", "McDonalds 2017",             "2017-07-01"),
    1471:  ("MCD18",  "B6", "McDonalds 2018",             "2018-07-01"),
    1472:  ("MCD19",  "B6", "McDonalds 2019",             "2019-07-01"),

    # ── Sword & Shield era (B7) ───────────────────────────────────────────
    2720:  ("PR-SW",  "B7", "SWSH Black Star Promos",     "2020-01-03"),
    2719:  ("SSH",    "B7", "Sword & Shield",             "2020-02-07"),
    2721:  ("RCL",    "B7", "Rebel Clash",                "2020-05-01"),
    2722:  ("DAA",    "B7", "Darkness Ablaze",            "2020-08-14"),
    2723:  ("CPA",    "B7", "Champion's Path",            "2020-09-25"),
    2724:  ("VIV",    "B7", "Vivid Voltage",              "2020-11-13"),
    2747:  ("SHF",    "B7", "Shining Fates",              "2021-02-19"),
    2781:  ("SHFSV",  "B7", "Shining Fates Shiny Vault",  "2021-02-19"),
    2765:  ("BST",    "B7", "Battle Styles",              "2021-03-19"),
    2807:  ("CRE",    "B7", "Chilling Reign",             "2021-06-18"),
    2848:  ("EVS",    "B7", "Evolving Skies",             "2021-08-27"),
    2867:  ("CEL",    "B7", "Celebrations",               "2021-10-08"),
    2931:  ("CELCC",  "B7", "Celebrations Classic Collection", "2021-10-08"),
    2906:  ("FST",    "B7", "Fusion Strike",              "2021-11-12"),
    2948:  ("BRS",    "B7", "Brilliant Stars",            "2022-02-25"),
    3020:  ("BRSTG",  "B7", "Brilliant Stars TG",        "2022-02-25"),
    3040:  ("ASR",    "B7", "Astral Radiance",            "2022-05-27"),
    3068:  ("ASRTG",  "B7", "Astral Radiance TG",        "2022-05-27"),
    3064:  ("PGO",    "B7", "Pokemon GO",                 "2022-07-01"),
    3118:  ("LOR",    "B7", "Lost Origin",                "2022-09-09"),
    3172:  ("LORTG",  "B7", "Lost Origin TG",            "2022-09-09"),
    3170:  ("SIT",    "B7", "Silver Tempest",             "2022-11-11"),
    17674: ("SITTG",  "B7", "Silver Tempest TG",         "2022-11-11"),
    17688: ("CRZ",    "B7", "Crown Zenith",               "2023-01-20"),
    17689: ("CRZGG",  "B7", "Crown Zenith GG",           "2023-01-20"),
    2782:  ("MCD21",  "B7", "McDonalds 25th Anniversary", "2021-06-11"),
    3150:  ("MCD22",  "B7", "McDonalds 2022",             "2022-08-01"),
    3179:  ("TOT22",  "B7", "Trick or Trade 2022",        "2022-10-01"),

    # Prize Packs (all series in one TCGCSV group → single DB set)
    22880: ("PRIZEPACK", "B7", "Prize Pack Series",       "2022-09-01"),

    # ── Scarlet & Violet era (B8) ─────────────────────────────────────────
    22872: ("SVP",    "B8", "Scarlet & Violet Promos",   "2023-01-01"),
    22873: ("SV1",    "B8", "Scarlet & Violet",          "2023-03-31"),
    23120: ("SV2",    "B8", "Paldea Evolved",            "2023-06-09"),
    23228: ("SV3",    "B8", "Obsidian Flames",           "2023-08-11"),
    23237: ("SV3PT5", "B8", "151",                       "2023-09-22"),
    23286: ("SV4",    "B8", "Paradox Rift",              "2023-11-03"),
    23353: ("SV4PT5", "B8", "Paldean Fates",             "2024-01-26"),
    23381: ("TEF",    "B8", "Temporal Forces",           "2024-03-22"),
    23473: ("TWM",    "B8", "Twilight Masquerade",       "2024-05-24"),
    23529: ("SFA",    "B8", "Shrouded Fable",            "2024-08-02"),
    23537: ("SCR",    "B8", "Stellar Crown",             "2024-09-13"),
    23651: ("SSP",    "B8", "Surging Sparks",            "2024-11-08"),
    23821: ("PRE",    "B8", "Prismatic Evolutions",      "2025-01-17"),
    24073: ("JTG",    "B8", "Journey Together",          "2025-03-28"),
    24269: ("DRI",    "B8", "Destined Rivals",           "2025-05-30"),
    24325: ("BLK",    "B8", "Black Bolt",                "2025-07-18"),
    24326: ("WHT",    "B8", "White Flare",               "2025-09-19"),
    24382: ("SVE",    "B8", "Scarlet & Violet Energies", "2023-03-31"),
    23306: ("MCD23",  "B8", "McDonalds 2023",            "2023-07-01"),
    24163: ("MCD24",  "B8", "McDonalds 2024",            "2024-07-01"),
    23323: ("TCGCL",  "B8", "TCG Classic",               "2023-10-01"),
    23266: ("TOT23",  "B8", "Trick or Trade 2023",       "2023-10-01"),
    23561: ("TOT24",  "B8", "Trick or Trade 2024",       "2024-10-01"),

    # ── Mega Evolution era (B9) ───────────────────────────────────────────
    24377: ("MEG",    "B9", "Mega Evolution",            "2024-05-01"),
    24378: ("PFL",    "B9", "Phantasmal Flames",         "2024-08-01"),
    24379: ("ASC",    "B9", "Ascended Heroes",           "2024-11-01"),
    24380: ("POR",    "B9", "Perfect Order",             "2025-02-01"),
    24451: ("MEP",    "B9", "Mega Evolution Promos",     "2024-05-01"),
    24461: ("MEE",    "B9", "Mega Evolution Energies",   "2024-05-01"),
    24655: ("CRI",    "B9", "Chaos Rising",              "2026-05-22"),
    24688: ("ME05",   "B9", "Pitch Black",               "2026-07-01"),
}

# Era metadata: era_code → (name, sort_order)
ERA_META: dict[str, tuple[str, int]] = {
    "B1": ("WotC Base Era",       1),
    "B2": ("EX Era",              2),
    "B3": ("Diamond & Pearl Era", 3),
    "B4": ("Black & White Era",   4),
    "B5": ("XY Era",              5),
    "B6": ("Sun & Moon Era",      6),
    "B7": ("Sword & Shield Era",  7),
    "B8": ("Scarlet & Violet Era",8),
    "B9": ("Mega Evolution Era",  9),
}

# These groupIds contain single-variant (Holo) sets → empty subTypeName maps to H
TG_GG_GROUPS: frozenset[int] = frozenset({
    3020, 3068, 3172, 17674, 17689,  # Trainer Galleries / GG
    22880,                            # Prize Pack
    2931,                            # Celebrations Classic Collection
    3179, 23266, 23561,              # Trick or Trade
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _round_up_50c(zar: Decimal) -> Decimal:
    """Round up to nearest R0.50."""
    return (Decimal(math.ceil(float(zar) * 2)) / 2).quantize(Decimal("0.50"))


def _to_zar(usd: float | str, rate: Decimal) -> Decimal:
    """Convert USD → ZAR with markup, rounded up to R0.50."""
    if not usd:
        return Decimal("0.00")
    return _round_up_50c(Decimal(str(usd)) * rate * MARKUP)


def _fetch_rate() -> Decimal:
    """Fetch live USD/ZAR exchange rate."""
    for url in RATE_APIS:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            zar = data.get("rates", {}).get("ZAR")
            if zar:
                return Decimal(str(zar))
        except Exception:
            continue
    raise RuntimeError("Could not fetch USD/ZAR rate from any fallback API.")


def _fetch_json(url: str) -> dict | list:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    # TCGCSV wraps results in {"results": [...]} sometimes
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def _get_number_from_extended(extended_data: list[dict]) -> str | None:
    """Extract card number from TCGCSV extendedData array."""
    for item in (extended_data or []):
        if item.get("name", "").lower() == "number":
            return str(item.get("value", "")).strip()
    return None


def _build_pb_id(set_code: str, variant: str, card_number: str, pokemon_number: str) -> str:
    """
    Build PokéBulk internal ID.
    Format: PB-{SET_CODE}-{VARIANT}-{CARD_NUMBER}
    e.g.   PB-BRS-RH-001
    """
    num = str(card_number or "000").zfill(3)
    return f"PB-{set_code.upper()}-{variant}-{num}"


# ---------------------------------------------------------------------------
# Core sync functions
# ---------------------------------------------------------------------------

def _get_or_create_era(era_code: str) -> "Era":
    """Get or create Era record from ERA_META."""
    name, sort_order = ERA_META.get(era_code, (f"Era {era_code}", 99))
    era, _ = Era.objects.get_or_create(
        code=era_code,
        defaults={"name": name, "sort_order": sort_order},
    )
    return era


def _get_or_create_card_set(
    db_code: str, era_code: str, set_name: str, release_date: str
) -> "CardSet":
    """Get or create CardSet. Always ensures era is set."""
    era = _get_or_create_era(era_code)
    card_set, created = CardSet.objects.get_or_create(
        code=db_code,
        defaults={
            "name": set_name,
            "era": era,
            "release_date": release_date,
        },
    )
    if not created and card_set.era != era:
        card_set.era = era
        card_set.save(update_fields=["era"])
    return card_set


def _sync_group(
    group_id: int,
    cfg: tuple[str, str, str, str],
    rate: Decimal,
    category: "Category",
    dry_run: bool,
    stdout,
    style,
) -> dict[str, int]:
    """
    Fetch products + prices for one TCGCSV group and upsert DB records.
    Returns stats dict.
    """
    db_code, era_code, set_name, release_date = cfg
    stats = {"created": 0, "updated": 0, "skipped": 0, "no_price": 0, "non_card": 0}

    # ── Ensure set exists ────────────────────────────────────────────────
    card_set = _get_or_create_card_set(db_code, era_code, set_name, release_date)
    is_tg_gg = group_id in TG_GG_GROUPS

    # ── Fetch products ───────────────────────────────────────────────────
    products_url = f"{TCGCSV_BASE}/{group_id}/products"
    try:
        products = _fetch_json(products_url)
    except Exception as exc:
        stdout.write(style.ERROR(f"  [products] fetch failed: {exc}"))
        return stats

    if not isinstance(products, list):
        stdout.write(style.ERROR(f"  [products] unexpected response type"))
        return stats

    # ── Fetch prices ─────────────────────────────────────────────────────
    prices_url = f"{TCGCSV_BASE}/{group_id}/prices"
    try:
        prices_raw = _fetch_json(prices_url)
    except Exception as exc:
        stdout.write(style.ERROR(f"  [prices] fetch failed: {exc}"))
        return stats

    # Build price lookup: productId → price row dict
    prices_by_pid: dict[int, dict] = {}
    for row in (prices_raw if isinstance(prices_raw, list) else []):
        pid = row.get("productId")
        if pid is not None:
            prices_by_pid[int(pid)] = row

    stdout.write(
        f"  {len(products)} products, {len(prices_by_pid)} price rows"
    )

    # ── Process each product ─────────────────────────────────────────────
    creates: list["PokemonProduct"] = []
    updates: list["PokemonProduct"] = []

    for prod in products:
        pid = prod.get("productId")
        if pid is None:
            continue
        pid = int(pid)

        # Filter: only cards (must have 'Number' in extendedData)
        extended = prod.get("extendedData") or []
        card_number = _get_number_from_extended(extended)
        if card_number is None:
            stats["non_card"] += 1
            continue

        # Name
        tcg_name = (prod.get("name") or "").strip()
        if not tcg_name:
            continue

        # Subtype → variant
        subtype = (prod.get("subTypeName") or "").strip()
        if is_tg_gg and subtype == "":
            variant = "H"
        else:
            variant = SUBTYPE_MAP.get(subtype, "N")

        # Rarity
        rarity_raw = ""
        for item in extended:
            if item.get("name", "").lower() == "rarity":
                rarity_raw = str(item.get("value", "")).strip()
                break
        rarity = RARITY_MAP.get(rarity_raw, "common")

        # Price
        price_row = prices_by_pid.get(pid)
        if not price_row:
            stats["no_price"] += 1
            # Still create the record — price syncs separately on nightly run
            usd_price = 0.0
        else:
            # Mid price preferred; fall back to market
            usd_price = (
                price_row.get("midPrice")
                or price_row.get("marketPrice")
                or price_row.get("lowPrice")
                or 0.0
            )

        zar_price = _to_zar(usd_price, rate)

        # Display name (suffix for RH/H variants)
        if variant == "RH":
            display_name = f"{tcg_name} (Reverse Holo)"
        elif variant == "H" and subtype not in ("Holofoil", "1st Edition Holofoil", "Unlimited Holofoil", ""):
            display_name = f"{tcg_name} (Holo)"
        else:
            display_name = tcg_name

        # Build pb_id
        pb_id = _build_pb_id(db_code, variant, card_number, card_number)

        # ── Upsert by tcgcsv_product_id (the gold key) ──────────────────
        try:
            existing = PokemonProduct.objects.get(tcgcsv_product_id=pid)
            changed = False
            if existing.price != zar_price and zar_price > 0:
                existing.price = zar_price
                changed = True
            if existing.card_set_id != card_set.pk:
                existing.card_set = card_set
                changed = True
            if existing.variant_override != variant:
                existing.variant_override = variant
                changed = True
            if changed:
                updates.append(existing)
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

        except PokemonProduct.DoesNotExist:
            # Create brand-new record
            new = PokemonProduct(
                pb_id=pb_id,
                name=display_name,
                card_set=card_set,
                category=category,
                rarity=rarity,
                card_number=card_number,
                variant_override=variant,
                tcgcsv_product_id=pid,
                price=zar_price,
                stock=1,
                is_active=True,
            )
            creates.append(new)
            stats["created"] += 1

        except PokemonProduct.MultipleObjectsReturned:
            # Duplicates exist — update the first, mark the rest inactive
            dupes = list(PokemonProduct.objects.filter(tcgcsv_product_id=pid).order_by("pk"))
            first = dupes[0]
            if first.price != zar_price and zar_price > 0:
                first.price = zar_price
                updates.append(first)
                stats["updated"] += 1
            else:
                stats["skipped"] += 1
            for dupe in dupes[1:]:
                dupe.is_active = False
                updates.append(dupe)

    # ── Bulk write ───────────────────────────────────────────────────────
    if not dry_run:
        if creates:
            PokemonProduct.objects.bulk_create(creates, ignore_conflicts=True)
        if updates:
            update_fields = ["price", "card_set", "variant_override", "is_active"]
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(updates, update_fields)

    return stats


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Sync card data + prices from TCGCSV into PokéBulk DB. "
        "TCGCSV is the master source — one DB record per product row, "
        "keyed by tcgcsv_product_id. No name matching."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--set-code",
            dest="set_code",
            default=None,
            help="Process only this set (e.g. BRS). Omit for all sets.",
        )
        parser.add_argument(
            "--rate",
            dest="rate",
            type=float,
            default=None,
            help="Override USD/ZAR exchange rate (e.g. 19.50).",
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=False,
            help="Simulate run — no DB writes.",
        )
        parser.add_argument(
            "--delay",
            dest="delay",
            type=float,
            default=0.3,
            help="Seconds to wait between group fetches (default 0.3).",
        )
        parser.add_argument(
            "--group-id",
            dest="group_id",
            type=int,
            default=None,
            help="Process only this TCGCSV groupId (for testing).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        delay: float = options["delay"]
        set_code: str | None = options["set_code"]
        group_id_only: int | None = options["group_id"]

        # ── Rate ─────────────────────────────────────────────────────────
        if options["rate"]:
            rate = Decimal(str(options["rate"]))
        else:
            self.stdout.write("Fetching USD/ZAR rate…")
            try:
                rate = _fetch_rate()
            except RuntimeError as exc:
                raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"1 USD = R{rate}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes"))

        # ── Category (Cards) ─────────────────────────────────────────────
        category, _ = Category.objects.get_or_create(
            slug="cards",
            defaults={"name": "Cards"},
        )

        # ── Build work list ───────────────────────────────────────────────
        if group_id_only:
            if group_id_only not in GROUP_CONFIG:
                raise CommandError(f"groupId {group_id_only} not in GROUP_CONFIG.")
            work = {group_id_only: GROUP_CONFIG[group_id_only]}
        elif set_code:
            sc = set_code.upper()
            work = {
                gid: cfg
                for gid, cfg in GROUP_CONFIG.items()
                if cfg[0].upper() == sc
            }
            if not work:
                raise CommandError(
                    f"Set code '{sc}' not found in GROUP_CONFIG. "
                    f"Available: {sorted(set(v[0] for v in GROUP_CONFIG.values()))}"
                )
        else:
            work = GROUP_CONFIG

        self.stdout.write(f"Processing {len(work)} group(s)…\n")

        # ── Totals ────────────────────────────────────────────────────────
        totals: dict[str, int] = {
            "created": 0, "updated": 0, "skipped": 0,
            "no_price": 0, "non_card": 0,
        }

        for i, (gid, cfg) in enumerate(work.items(), 1):
            db_code, era_code, set_name, _ = cfg
            self.stdout.write(
                f"[{i}/{len(work)}] {db_code} — {set_name} (group {gid})"
            )

            stats = _sync_group(
                group_id=gid,
                cfg=cfg,
                rate=rate,
                category=category,
                dry_run=dry_run,
                stdout=self.stdout,
                style=self.style,
            )

            for k in totals:
                totals[k] += stats[k]

            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ created={stats['created']}  updated={stats['updated']}  "
                    f"skipped={stats['skipped']}  no_price={stats['no_price']}  "
                    f"non_card={stats['non_card']}"
                )
            )

            if i < len(work):
                time.sleep(delay)

        # ── Summary ───────────────────────────────────────────────────────
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"DONE  "
                f"created={totals['created']}  "
                f"updated={totals['updated']}  "
                f"skipped={totals['skipped']}  "
                f"no_price={totals['no_price']}  "
                f"non_card={totals['non_card']}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — nothing written to DB."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Net new cards in DB: {totals['created']}"
                )
            )
