"""
sync_tcgcsv — PokeBulk SA
=========================
Syncs cards from TCGCSV into the Django DB.
- Uses correct group IDs sourced directly from all_tcg_products xlsx
- Nightly price updates by tcgcsv_product_id
- ignore_conflicts=True so restarts are always safe

USAGE
-----
  python manage.py sync_tcgcsv
  python manage.py sync_tcgcsv --set-code MEG
  python manage.py sync_tcgcsv --dry-run
  python manage.py sync_tcgcsv --rate 19.50
  python manage.py sync_tcgcsv --delay 0.5

SUBTYPE → VARIANT
  Normal / 1st Edition Normal / Unlimited Normal  → N
  Holofoil / 1st Edition Holofoil / Unlimited Holofoil → H
  Reverse Holofoil → RH
  "" (empty) → H   (TG / GG / Prize Pack single-variant sets)
"""

import math
import time
import requests
from decimal import Decimal, ROUND_UP
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from products.models import PokemonProduct, CardSet, Era, Category

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")

RATE_APIS = [
    "https://api.exchangerate-api.com/v4/latest/USD",
    "https://open.er-api.com/v6/latest/USD",
]

# ---------------------------------------------------------------------------
# ALL sets with CORRECT group IDs sourced from all_tcg_products xlsx
# Format: "SET_CODE": (group_id, "Set Name")
# ---------------------------------------------------------------------------
GROUP_CONFIG = {
    "BS":      (604,   "Base Set"),
    "BS2":     (605,   "Base Set 2"),
    "FO":      (630,   "Fossil"),
    "JU":      (635,   "Jungle"),
    "SI1":     (648,   "Southern Islands"),
    "MT":      (1368,  "Mysterious Treasures"),
    "SF":      (1369,  "Stormfront"),
    "PLB":     (1370,  "Plasma Blast"),
    "SK":      (1372,  "Skyridge"),
    "TR":      (1373,  "Team Rocket"),
    "LC":      (1374,  "Legendary Collection"),
    "EX":      (1375,  "Expedition Base Set"),
    "DR":      (1376,  "Dragon"),
    "MA":      (1377,  "Team Magma vs Team Aqua"),
    "LM":      (1378,  "Legend Maker"),
    "HP":      (1379,  "Holon Phantoms"),
    "TM":      (1381,  "Triumphant"),
    "PLF":     (1382,  "Plasma Freeze"),
    "PK":      (1383,  "Power Keepers"),
    "SV":      (1384,  "Supreme Victors"),
    "NVI":     (1385,  "Noble Victories"),
    "DEX":     (1386,  "Dark Explorers"),
    "XY":      (1387,  "XY Base Set"),
    "N3":      (1389,  "Neo Revelation"),
    "MD":      (1390,  "Majestic Dawn"),
    "AR":      (1391,  "Arceus"),
    "SS":      (1392,  "Sandstorm"),
    "RS":      (1393,  "Ruby & Sapphire"),
    "DRX":     (1394,  "Dragons Exalted"),
    "CG":      (1395,  "Crystal Guardians"),
    "N1":      (1396,  "Neo Genesis"),
    "AQ":      (1397,  "Aquapolis"),
    "UF":      (1398,  "Unseen Forces"),
    "UL":      (1399,  "Unleashed"),
    "BLW":     (1400,  "Black & White"),
    "MCD11":   (1401,  "McDonalds 2011"),
    "HS":      (1402,  "HeartGold & SoulSilver"),
    "UD":      (1403,  "Undaunted"),
    "DX":      (1404,  "Deoxys"),
    "GE":      (1405,  "Great Encounters"),
    "PL":      (1406,  "Platinum"),
    "PR-BLW":  (1407,  "BW Black Star Promos"),
    "BCR":     (1408,  "Boundaries Crossed"),
    "LTR":     (1409,  "Legendary Treasures"),
    "EM":      (1410,  "Emerald"),
    "DF":      (1411,  "Dragon Frontiers"),
    "NXD":     (1412,  "Next Destinies"),
    "PLS":     (1413,  "Plasma Storm"),
    "POP7":    (1414,  "POP Series 7"),
    "CoL":     (1415,  "Call of Legends"),
    "HL":      (1416,  "Hidden Legends"),
    "LA":      (1417,  "Legends Awakened"),
    "PR-WB":   (1418,  "Wizards Black Star Promos"),
    "RG":      (1419,  "FireRed & LeafGreen"),
    "G1":      (1441,  "Gym Heroes"),
    "G2":      (1440,  "Gym Challenge"),
    "PR-HS":   (1453,  "HGSS Black Star Promos"),
    "PR-NB":   (1423,  "Nintendo Black Star Promos"),
    "N2":      (1434,  "Neo Discovery"),
    "N4":      (1444,  "Neo Destiny"),
    "EPO":     (1424,  "Emerging Powers"),
    "TRR":     (1428,  "Team Rocket Returns"),
    "DS":      (1429,  "Delta Species"),
    "DP":      (1430,  "Diamond & Pearl"),
    "POP1":    (1427,  "POP Series 1"),
    "POP2":    (1428,  "POP Series 2"),
    "POP3":    (1429,  "POP Series 3"),
    "POP4":    (1430,  "POP Series 4"),
    "SW":      (1434,  "Secret Wonders"),
    "FLF":     (1464,  "Flashfire"),
    "FFI":     (1481,  "Furious Fists"),
    "PHF":     (1494,  "Phantom Forces"),
    "PRC":     (1509,  "Primal Clash"),
    "DCR":     (1525,  "Double Crisis"),
    "ROS":     (1534,  "Roaring Skies"),
    "AOR":     (1576,  "Ancient Origins"),
    "BKT":     (1661,  "BREAKthrough"),
    "BSS":     (1663,  "Base Set Shadowless"),
    "BKP":     (1701,  "BREAKpoint"),
    "GEN":     (1728,  "Generations"),
    "FCO":     (1780,  "Fates Collide"),
    "STS":     (1815,  "Steam Siege"),
    "EVO":     (1842,  "Evolutions"),
    "SM01":    (1863,  "Sun & Moon Base Set"),
    "SM02":    (1919,  "Guardians Rising"),
    "SM03":    (1957,  "Burning Shadows"),
    "SHL":     (2054,  "Shining Legends"),
    "SM04":    (2071,  "Crimson Invasion"),
    "SM05":    (2178,  "Ultra Prism"),
    "SM06":    (2209,  "Forbidden Light"),
    "CES":     (2278,  "Celestial Storm"),
    "DRM":     (2295,  "Dragon Majesty"),
    "SM8":     (2328,  "Lost Thunder"),
    "SM9":     (2377,  "Team Up"),
    "SM10":    (2420,  "Unbroken Bonds"),
    "SM11":    (2464,  "Unified Minds"),
    "HIF":     (2480,  "Hidden Fates"),
    "SM12":    (2534,  "Cosmic Eclipse"),
    "SWSH01":  (2585,  "Sword & Shield"),
    "HIFSV":   (2594,  "Hidden Fates Shiny Vault"),
    "SWSH02":  (2626,  "Rebel Clash"),
    "SWSH03":  (2675,  "Darkness Ablaze"),
    "CHP":     (2685,  "Champion's Path"),
    "SWSH04":  (2701,  "Vivid Voltage"),
    "SHF":     (2754,  "Shining Fates"),
    "SWSH05":  (2765,  "Battle Styles"),
    "SHFSV":   (2781,  "Shining Fates Shiny Vault"),
    "MCD21":   (2782,  "McDonalds 25th Anniversary"),
    "SWSH06":  (2807,  "Chilling Reign"),
    "SWSH07":  (2848,  "Evolving Skies"),
    "CLB":     (2867,  "Celebrations"),
    "SWSH08":  (2906,  "Fusion Strike"),
    "CCC":     (2931,  "Celebrations Classic Collection"),
    "SWSH09":  (2948,  "Brilliant Stars"),
    "BST":     (3020,  "Brilliant Stars Trainer Gallery"),
    "SWSH10":  (3040,  "Astral Radiance"),
    "PGO":     (3064,  "Pokemon GO"),
    "ASRTG":   (3068,  "Astral Radiance Trainer Gallery"),
    "SWSH11":  (3118,  "Lost Origin"),
    "LORTG":   (3172,  "Lost Origin Trainer Gallery"),
    "SWSH12":  (3170,  "Silver Tempest"),
    "ST":      (17674, "Silver Tempest Trainer Gallery"),
    "CRZ":     (17688, "Crown Zenith"),
    "CRZGG":   (17689, "Crown Zenith Galarian Gallery"),
    "MCD22":   (3150,  "McDonalds 2022"),
    "TOT22":   (3179,  "Trick or Trade 2022"),
    "PRIZEPACK":(22880,"Prize Pack Series"),
    "SVP":     (22872, "Scarlet & Violet Promos"),
    "SVI":     (22873, "Scarlet & Violet"),
    "PAL":     (23120, "Paldea Evolved"),
    "OBF":     (23228, "Obsidian Flames"),
    "MEW":     (23237, "Scarlet & Violet 151"),
    "PAR":     (23286, "Paradox Rift"),
    "PAF":     (23353, "Paldean Fates"),
    "TEF":     (23381, "Temporal Forces"),
    "TOT23":   (23266, "Trick or Trade 2023"),
    "TCGCL":   (23323, "TCG Classic"),
    "MCD23":   (23306, "McDonalds 2023"),
    "TWM":     (23473, "Twilight Masquerade"),
    "SFA":     (23529, "Shrouded Fable"),
    "SCR":     (23537, "Stellar Crown"),
    "SSP":     (23651, "Surging Sparks"),
    "PRE":     (23821, "Prismatic Evolutions"),
    "JTG":     (24073, "Journey Together"),
    "DRI":     (24269, "Destined Rivals"),
    "BLK":     (24325, "Black Bolt"),
    "WHT":     (24326, "White Flare"),
    "MEG":     (24380, "Mega Evolution"),
    "SVE":     (24382, "Scarlet & Violet Energies"),
    "PFL":     (24448, "Phantasmal Flames"),
    "MEP":     (24451, "Mega Evolution Promos"),
    "MEE":     (24461, "Mega Evolution Energies"),
    "ASC":     (24541, "Ascended Heroes"),
    "POR":     (24587, "Perfect Order"),
    "MCD24":   (24163, "McDonalds 2024"),
    "TOT24":   (23561, "Trick or Trade 2024"),
    "CRI":     (24655, "Chaos Rising"),
}

# ---------------------------------------------------------------------------
# Era mapping — which era each set belongs to
# ---------------------------------------------------------------------------
ERA_MAP = {
    "BS": "Base", "BS2": "Base", "JU": "Base", "FO": "Base", "TR": "Base",
    "G1": "Base", "G2": "Base", "SI1": "Base", "PR-WB": "Base",
    "N1": "Base", "N2": "Base", "N3": "Base", "N4": "Base", "LC": "Base",
    "BSS": "Base",
    "EX": "EX", "AQ": "EX", "SK": "EX", "RS": "EX", "SS": "EX",
    "DR": "EX", "MA": "EX", "HL": "EX", "RG": "EX", "TRR": "EX",
    "DX": "EX", "EM": "EX", "UF": "EX", "DS": "EX", "LM": "EX",
    "HP": "EX", "CG": "EX", "DF": "EX", "PK": "EX", "PR-NB": "EX",
    "POP1": "EX", "POP2": "EX", "POP3": "EX", "POP4": "EX",
    "DP": "DP/HGSS", "MT": "DP/HGSS", "SW": "DP/HGSS", "GE": "DP/HGSS",
    "MD": "DP/HGSS", "LA": "DP/HGSS", "SF": "DP/HGSS", "PL": "DP/HGSS",
    "RR": "DP/HGSS", "SV": "DP/HGSS", "AR": "DP/HGSS", "PR-HS": "DP/HGSS",
    "POP7": "DP/HGSS", "HS": "DP/HGSS", "UL": "DP/HGSS", "UD": "DP/HGSS",
    "TM": "DP/HGSS", "CoL": "DP/HGSS",
    "BLW": "Black & White", "EPO": "Black & White", "NVI": "Black & White",
    "NXD": "Black & White", "DEX": "Black & White", "DRX": "Black & White",
    "DRV": "Black & White", "BCR": "Black & White", "PLS": "Black & White",
    "PLF": "Black & White", "PLB": "Black & White", "LTR": "Black & White",
    "PR-BLW": "Black & White", "MCD11": "Black & White", "MCD12": "Black & White",
    "XY": "XY", "FLF": "XY", "FFI": "XY", "PHF": "XY", "PRC": "XY",
    "DCR": "XY", "ROS": "XY", "AOR": "XY", "BKT": "XY", "BKP": "XY",
    "GEN": "XY", "FCO": "XY", "STS": "XY", "EVO": "XY", "PR-XY": "XY",
    "MCD14": "XY", "MCD15": "XY", "MCD16": "XY",
    "SM01": "Sun & Moon", "SM02": "Sun & Moon", "SM03": "Sun & Moon",
    "SHL": "Sun & Moon", "SM04": "Sun & Moon", "SM05": "Sun & Moon",
    "SM06": "Sun & Moon", "CES": "Sun & Moon", "DRM": "Sun & Moon",
    "SM8": "Sun & Moon", "SM9": "Sun & Moon", "SM10": "Sun & Moon",
    "SM11": "Sun & Moon", "HIF": "Sun & Moon", "HIFSV": "Sun & Moon",
    "SM12": "Sun & Moon", "MCD17": "Sun & Moon", "MCD18": "Sun & Moon",
    "MCD19": "Sun & Moon",
    "SWSH01": "Sword & Shield", "SWSH02": "Sword & Shield", "SWSH03": "Sword & Shield",
    "CHP": "Sword & Shield", "SWSH04": "Sword & Shield", "SHF": "Sword & Shield",
    "SHFSV": "Sword & Shield", "SWSH05": "Sword & Shield", "SWSH06": "Sword & Shield",
    "SWSH07": "Sword & Shield", "CLB": "Sword & Shield", "CCC": "Sword & Shield",
    "SWSH08": "Sword & Shield", "SWSH09": "Sword & Shield", "BST": "Sword & Shield",
    "SWSH10": "Sword & Shield", "PGO": "Sword & Shield", "ASRTG": "Sword & Shield",
    "SWSH11": "Sword & Shield", "LORTG": "Sword & Shield", "SWSH12": "Sword & Shield",
    "ST": "Sword & Shield", "CRZ": "Sword & Shield", "CRZGG": "Sword & Shield",
    "MCD21": "Sword & Shield", "MCD22": "Sword & Shield", "TOT22": "Sword & Shield",
    "SVP": "Scarlet & Violet", "SVI": "Scarlet & Violet", "PAL": "Scarlet & Violet",
    "OBF": "Scarlet & Violet", "MEW": "Scarlet & Violet", "PAR": "Scarlet & Violet",
    "PAF": "Scarlet & Violet", "TEF": "Scarlet & Violet", "TWM": "Scarlet & Violet",
    "SFA": "Scarlet & Violet", "SCR": "Scarlet & Violet", "SSP": "Scarlet & Violet",
    "PRE": "Scarlet & Violet", "JTG": "Scarlet & Violet", "DRI": "Scarlet & Violet",
    "BLK": "Scarlet & Violet", "WHT": "Scarlet & Violet", "SVE": "Scarlet & Violet",
    "PRIZEPACK": "Scarlet & Violet", "MCD23": "Scarlet & Violet",
    "MCD24": "Scarlet & Violet", "TOT23": "Scarlet & Violet",
    "TOT24": "Scarlet & Violet", "TCGCL": "Scarlet & Violet",
    "MEG": "Mega Evolution", "PFL": "Mega Evolution", "ASC": "Mega Evolution",
    "POR": "Mega Evolution", "MEP": "Mega Evolution", "MEE": "Mega Evolution",
    "CRI": "Mega Evolution",
}

SUBTYPE_MAP = {
    "Normal":               "N",
    "Holofoil":             "H",
    "Reverse Holofoil":     "RH",
    "1st Edition Normal":   "N",
    "1st Edition Holofoil": "H",
    "Unlimited Normal":     "N",
    "Unlimited Holofoil":   "H",
    "":                     "H",
}

RARITY_MAP = {
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
    "Shiny Rare":                    "shiny_rare",
    "Shiny Ultra Rare":              "shiny_ultra_rare",
    "Rare Secret":                   "secret_rare",
    "Rare Rainbow":                  "hyper_rare",
    "Rare Shining":                  "holo_rare",
    "Rare Shiny":                    "shiny_rare",
    "Rare Shiny GX":                 "shiny_ultra_rare",
    "Rare Prism Star":               "ultra_rare",
    "Amazing Rare":                  "ultra_rare",
    "Trainer Gallery Rare Holo":     "holo_rare",
    "Trainer Gallery Ultra Rare":    "ultra_rare",
    "Trainer Gallery Secret Rare":   "secret_rare",
    "Classic Collection":            "holo_rare",
    "ACE SPEC Rare":                 "ultra_rare",
}


def _get_rate(override=None):
    if override:
        return Decimal(str(override))
    for url in RATE_APIS:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            rates = data.get("rates") or data.get("conversion_rates", {})
            if "ZAR" in rates:
                return Decimal(str(rates["ZAR"]))
        except Exception:
            continue
    raise CommandError("Could not fetch USD/ZAR rate from any API.")


def _zar_price(usd, rate):
    if usd is None:
        return None
    raw = Decimal(str(usd)) * rate * MARKUP
    cents = (raw * 2).quantize(Decimal("1"), rounding=ROUND_UP)
    return cents / 2


def _get_or_create_era(era_name):
    era, _ = Era.objects.get_or_create(
        code=era_name,
        defaults={"name": era_name},
    )
    return era


def _get_or_create_card_set(set_code, era_name, set_name, release_date=None):
    era = _get_or_create_era(era_name)
    defaults = {"name": set_name, "era": era}
    if release_date:
        defaults["release_date"] = release_date
    card_set, _ = CardSet.objects.get_or_create(
        code=set_code,
        defaults=defaults,
    )
    return card_set


def _parse_card_number(raw):
    if not raw:
        return None
    raw = str(raw).strip()
    # Strip "001/132" format → "001"
    if "/" in raw:
        raw = raw.split("/")[0]
    # Strip leading zeros for numeric
    try:
        return str(int(raw))
    except ValueError:
        # Non-numeric like "DP50", "SWSH001" — skip
        return None


def _sync_group(set_code, group_id, set_name, era_name, rate, dry_run, style):
    created = updated = skipped = no_price = non_card = 0

    # Fetch products
    try:
        r = requests.get(f"{TCGCSV_BASE}/{group_id}/products", headers=HEADERS, timeout=30)
        r.raise_for_status()
        products = r.json().get("results", [])
    except Exception as e:
        print(f"  [products] fetch failed: {e}")
        return dict(created=0, updated=0, skipped=0, no_price=0, non_card=0)

    # Fetch prices
    prices = {}
    try:
        r = requests.get(f"{TCGCSV_BASE}/{group_id}/prices", headers=HEADERS, timeout=30)
        r.raise_for_status()
        for row in r.json().get("results", []):
            pid = row.get("productId")
            sub = row.get("subTypeName", "")
            mkt = row.get("marketPrice")
            low = row.get("lowPrice")
            prices[(pid, sub)] = mkt or low
    except Exception as e:
        print(f"  [prices] fetch failed: {e}")

    print(f"  {len(products)} products, {len(prices)} price rows")

    card_set = _get_or_create_card_set(set_code, era_name, set_name)
    category, _ = Category.objects.get_or_create(name="Pokemon")

    to_create = []

    for p in products:
        pid = p.get("productId")
        name = (p.get("name") or "").strip()
        sub = (p.get("subTypeName") or "").strip()
        rarity_raw = (p.get("rarityName") or "").strip()
        number_raw = p.get("number") or p.get("extNumber") or ""
        image_url = p.get("imageUrl") or p.get("image_url") or ""

        # Must be a card subtype
        if sub not in SUBTYPE_MAP:
            non_card += 1
            continue

        card_number = _parse_card_number(number_raw)
        if card_number is None:
            non_card += 1
            continue

        variant = SUBTYPE_MAP[sub]
        rarity = RARITY_MAP.get(rarity_raw, "common")
        usd_price = prices.get((pid, sub))

        if usd_price is None:
            no_price += 1

        zar = _zar_price(usd_price, rate) if usd_price else None

        # pb_id format: SETCODE-CARDNUM-VARIANT
        pb_id = f"{set_code}-{card_number}-{variant}"

        if dry_run:
            print(f"    [DRY] {pb_id} | {name} | R{zar}")
            created += 1
            continue

        # Check if already exists
        if PokemonProduct.objects.filter(pb_id=pb_id).exists():
            skipped += 1
            continue

        to_create.append(PokemonProduct(
            pb_id=pb_id,
            tcgcsv_product_id=pid,
            name=name,
            card_number=card_number,
            card_set=card_set,
            category=category,
            variant_override=variant,
            rarity=rarity,
            image_url=image_url,
            price_zar=zar,
            stock=0,
        ))

    if to_create and not dry_run:
        with transaction.atomic():
            result = PokemonProduct.objects.bulk_create(to_create, ignore_conflicts=True)
            created = len(result)

    return dict(created=created, updated=updated, skipped=skipped,
                no_price=no_price, non_card=non_card)


class Command(BaseCommand):
    help = "Sync cards from TCGCSV into Railway DB"

    def add_arguments(self, parser):
        parser.add_argument("--set-code", type=str, help="Sync only this set code")
        parser.add_argument("--dry-run", action="store_true", help="Preview only")
        parser.add_argument("--rate", type=float, help="Override USD/ZAR rate")
        parser.add_argument("--delay", type=float, default=0.1,
                            help="Seconds between group requests (default 0.1)")

    def handle(self, *args, **options):
        set_code_filter = options.get("set_code")
        dry_run = options.get("dry_run", False)
        delay = options.get("delay", 0.1)

        self.stdout.write("Fetching USD/ZAR rate…")
        rate = _get_rate(options.get("rate"))
        self.stdout.write(f"1 USD = R{rate:.2f}\n")

        config = GROUP_CONFIG
        if set_code_filter:
            if set_code_filter not in config:
                raise CommandError(f"Unknown set code: {set_code_filter}")
            config = {set_code_filter: config[set_code_filter]}

        total = len(config)
        self.stdout.write(f"Processing {total} group(s)…")

        grand = dict(created=0, updated=0, skipped=0, no_price=0, non_card=0)

        for i, (code, (gid, sname)) in enumerate(config.items(), 1):
            era_name = ERA_MAP.get(code, "Other")
            self.stdout.write(f"[{i}/{total}] {code} — {sname} (group {gid})")
            stats = _sync_group(
                set_code=code,
                group_id=gid,
                set_name=sname,
                era_name=era_name,
                rate=rate,
                dry_run=dry_run,
                style=self.style,
            )
            self.stdout.write(
                f"  ✓ created={stats['created']}  updated={stats['updated']}"
                f"  skipped={stats['skipped']}  no_price={stats['no_price']}"
                f"  non_card={stats['non_card']}"
            )
            for k in grand:
                grand[k] += stats[k]
            if delay:
                time.sleep(delay)

        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(
            f"DONE  created={grand['created']}  updated={grand['updated']}"
            f"  skipped={grand['skipped']}  no_price={grand['no_price']}"
            f"  non_card={grand['non_card']}"
        )
        self.stdout.write(f"Net new cards in DB: {grand['created']}")
