"""
sync_tcgcsv — PokeBulk SA
Syncs cards from TCGCSV into Railway DB.
- productId is the unique key
- card_number must be integer (skip alphanumeric like SH1, SWSH001)
- Era codes: B1-B9 matching existing Railway eras
- price field (not price_zar)
- Variants from prices endpoint subTypeName
"""

import time
import requests
from decimal import Decimal, ROUND_UP
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from products.models import PokemonProduct, CardSet, Era, Category

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}
MARKUP = Decimal("1.10")

RATE_APIS = [
    "https://api.exchangerate-api.com/v4/latest/USD",
    "https://open.er-api.com/v6/latest/USD",
]

# Era codes matching Railway DB exactly: B1-B9
ERA_CODES = {
    "B1": "WotC Base Era",
    "B2": "EX Era",
    "B3": "Diamond & Pearl Era",
    "B4": "Black & White Era",
    "B5": "XY Era",
    "B6": "Sun & Moon Era",
    "B7": "Sword & Shield Era",
    "B8": "Scarlet & Violet Era",
    "B9": "Mega Evolution Era",
}

# All sets: code -> (group_id, set_name, era_code)
GROUP_CONFIG = {
    "BS":       (604,   "Base Set",                        "B1"),
    "BS2":      (605,   "Base Set 2",                      "B1"),
    "FO":       (630,   "Fossil",                          "B1"),
    "JU":       (635,   "Jungle",                          "B1"),
    "SI1":      (648,   "Southern Islands",                "B1"),
    "TR":       (1373,  "Team Rocket",                     "B1"),
    "LC":       (1374,  "Legendary Collection",            "B1"),
    "N3":       (1389,  "Neo Revelation",                  "B1"),
    "N1":       (1396,  "Neo Genesis",                     "B1"),
    "N2":       (1434,  "Neo Discovery",                   "B1"),
    "G2":       (1440,  "Gym Challenge",                   "B1"),
    "G1":       (1441,  "Gym Heroes",                      "B1"),
    "N4":       (1444,  "Neo Destiny",                     "B1"),
    "PR-WB":    (1418,  "Wizards Black Star Promos",       "B1"),
    "BSS":      (1663,  "Base Set Shadowless",             "B1"),
    "SK":       (1372,  "Skyridge",                        "B2"),
    "EX":       (1375,  "Expedition Base Set",             "B2"),
    "DR":       (1376,  "Dragon",                          "B2"),
    "MA":       (1377,  "Team Magma vs Team Aqua",         "B2"),
    "LM":       (1378,  "Legend Maker",                    "B2"),
    "HP":       (1379,  "Holon Phantoms",                  "B2"),
    "PK":       (1383,  "Power Keepers",                   "B2"),
    "SS":       (1392,  "Sandstorm",                       "B2"),
    "RS":       (1393,  "Ruby & Sapphire",                 "B2"),
    "CG":       (1395,  "Crystal Guardians",               "B2"),
    "AQ":       (1397,  "Aquapolis",                       "B2"),
    "DX":       (1404,  "Deoxys",                          "B2"),
    "EM":       (1410,  "Emerald",                         "B2"),
    "DF":       (1411,  "Dragon Frontiers",                "B2"),
    "HL":       (1416,  "Hidden Legends",                  "B2"),
    "LA":       (1417,  "Legends Awakened",                "B2"),
    "RG":       (1419,  "FireRed & LeafGreen",             "B2"),
    "PR-NB":    (1423,  "Nintendo Black Star Promos",      "B2"),
    "TRR":      (1428,  "Team Rocket Returns",             "B2"),
    "DS":       (1429,  "Delta Species",                   "B2"),
    "POP1":     (1427,  "POP Series 1",                    "B2"),
    "UF":       (1398,  "Unseen Forces",                   "B3"),
    "MD":       (1390,  "Majestic Dawn",                   "B3"),
    "AR":       (1391,  "Arceus",                          "B3"),
    "SF":       (1369,  "Stormfront",                      "B3"),
    "MT":       (1368,  "Mysterious Treasures",            "B3"),
    "GE":       (1405,  "Great Encounters",                "B3"),
    "PL":       (1406,  "Platinum",                        "B3"),
    "RR":       (1367,  "Rising Rivals",                   "B3"),
    "SV":       (1384,  "Supreme Victors",                 "B3"),
    "CoL":      (1415,  "Call of Legends",                 "B3"),
    "HS":       (1402,  "HeartGold & SoulSilver",          "B3"),
    "UD":       (1403,  "Undaunted",                       "B3"),
    "TM":       (1381,  "Triumphant",                      "B3"),
    "UL":       (1399,  "Unleashed",                       "B3"),
    "PR-HS":    (1453,  "HGSS Black Star Promos",          "B3"),
    "POP7":     (1414,  "POP Series 7",                    "B3"),
    "DP":       (1430,  "Diamond & Pearl",                 "B3"),
    "SW":       (1434,  "Secret Wonders",                  "B3"),
    "MCD11":    (1401,  "McDonalds 2011",                  "B3"),
    "BLW":      (1400,  "Black & White",                   "B4"),
    "EPO":      (1424,  "Emerging Powers",                 "B4"),
    "NVI":      (1385,  "Noble Victories",                 "B4"),
    "NXD":      (1412,  "Next Destinies",                  "B4"),
    "DEX":      (1386,  "Dark Explorers",                  "B4"),
    "DRX":      (1394,  "Dragons Exalted",                 "B4"),
    "BCR":      (1408,  "Boundaries Crossed",              "B4"),
    "PLS":      (1413,  "Plasma Storm",                    "B4"),
    "PLF":      (1382,  "Plasma Freeze",                   "B4"),
    "PLB":      (1370,  "Plasma Blast",                    "B4"),
    "LTR":      (1409,  "Legendary Treasures",             "B4"),
    "PR-BLW":   (1407,  "BW Black Star Promos",            "B4"),
    "MCD12":    (1440,  "McDonalds 2012",                  "B4"),
    "XY":       (1387,  "XY Base Set",                     "B5"),
    "FLF":      (1464,  "Flashfire",                       "B5"),
    "FFI":      (1481,  "Furious Fists",                   "B5"),
    "PHF":      (1494,  "Phantom Forces",                  "B5"),
    "PRC":      (1509,  "Primal Clash",                    "B5"),
    "DCR":      (1525,  "Double Crisis",                   "B5"),
    "ROS":      (1534,  "Roaring Skies",                   "B5"),
    "AOR":      (1576,  "Ancient Origins",                 "B5"),
    "BKT":      (1661,  "BREAKthrough",                    "B5"),
    "BKP":      (1701,  "BREAKpoint",                      "B5"),
    "GEN":      (1728,  "Generations",                     "B5"),
    "FCO":      (1780,  "Fates Collide",                   "B5"),
    "STS":      (1815,  "Steam Siege",                     "B5"),
    "EVO":      (1842,  "Evolutions",                      "B5"),
    "PR-XY":    (1441,  "XY Black Star Promos",            "B5"),
    "SM01":     (1863,  "Sun & Moon",                      "B6"),
    "SM02":     (1919,  "Guardians Rising",                "B6"),
    "SM03":     (1957,  "Burning Shadows",                 "B6"),
    "SHL":      (2054,  "Shining Legends",                 "B6"),
    "SM04":     (2071,  "Crimson Invasion",                "B6"),
    "SM05":     (2178,  "Ultra Prism",                     "B6"),
    "SM06":     (2209,  "Forbidden Light",                 "B6"),
    "CES":      (2278,  "Celestial Storm",                 "B6"),
    "DRM":      (2295,  "Dragon Majesty",                  "B6"),
    "SM8":      (2328,  "Lost Thunder",                    "B6"),
    "SM9":      (2377,  "Team Up",                         "B6"),
    "SM10":     (2420,  "Unbroken Bonds",                  "B6"),
    "SM11":     (2464,  "Unified Minds",                   "B6"),
    "HIF":      (2480,  "Hidden Fates",                    "B6"),
    "HIFSV":    (2594,  "Hidden Fates Shiny Vault",        "B6"),
    "SM12":     (2534,  "Cosmic Eclipse",                  "B6"),
    "SWSH01":   (2585,  "Sword & Shield",                  "B7"),
    "SWSH02":   (2626,  "Rebel Clash",                     "B7"),
    "SWSH03":   (2675,  "Darkness Ablaze",                 "B7"),
    "CHP":      (2685,  "Champion's Path",                 "B7"),
    "SWSH04":   (2701,  "Vivid Voltage",                   "B7"),
    "SHF":      (2754,  "Shining Fates",                   "B7"),
    "SWSH05":   (2765,  "Battle Styles",                   "B7"),
    "SHFSV":    (2781,  "Shining Fates Shiny Vault",       "B7"),
    "MCD21":    (2782,  "McDonalds 25th Anniversary",      "B7"),
    "SWSH06":   (2807,  "Chilling Reign",                  "B7"),
    "SWSH07":   (2848,  "Evolving Skies",                  "B7"),
    "CLB":      (2867,  "Celebrations",                    "B7"),
    "SWSH08":   (2906,  "Fusion Strike",                   "B7"),
    "CCC":      (2931,  "Celebrations Classic Collection", "B7"),
    "SWSH09":   (2948,  "Brilliant Stars",                 "B7"),
    "BST":      (3020,  "Brilliant Stars Trainer Gallery", "B7"),
    "SWSH10":   (3040,  "Astral Radiance",                 "B7"),
    "PGO":      (3064,  "Pokemon GO",                      "B7"),
    "ASRTG":    (3068,  "Astral Radiance Trainer Gallery", "B7"),
    "SWSH11":   (3118,  "Lost Origin",                     "B7"),
    "LORTG":    (3172,  "Lost Origin Trainer Gallery",     "B7"),
    "SWSH12":   (3170,  "Silver Tempest",                  "B7"),
    "ST":       (17674, "Silver Tempest Trainer Gallery",  "B7"),
    "CRZ":      (17688, "Crown Zenith",                    "B7"),
    "CRZGG":    (17689, "Crown Zenith Galarian Gallery",   "B7"),
    "MCD22":    (3150,  "McDonalds 2022",                  "B7"),
    "TOT22":    (3179,  "Trick or Trade 2022",             "B7"),
    "SVP":      (22872, "Scarlet & Violet Promos",         "B8"),
    "SVI":      (22873, "Scarlet & Violet",                "B8"),
    "PAL":      (23120, "Paldea Evolved",                  "B8"),
    "OBF":      (23228, "Obsidian Flames",                 "B8"),
    "MEW":      (23237, "Scarlet & Violet 151",            "B8"),
    "PAR":      (23286, "Paradox Rift",                    "B8"),
    "PAF":      (23353, "Paldean Fates",                   "B8"),
    "TEF":      (23381, "Temporal Forces",                 "B8"),
    "MCD23":    (23306, "McDonalds 2023",                  "B8"),
    "TCGCL":    (23323, "TCG Classic",                     "B8"),
    "TOT23":    (23266, "Trick or Trade 2023",             "B8"),
    "TWM":      (23473, "Twilight Masquerade",             "B8"),
    "SFA":      (23529, "Shrouded Fable",                  "B8"),
    "SCR":      (23537, "Stellar Crown",                   "B8"),
    "TOT24":    (23561, "Trick or Trade 2024",             "B8"),
    "SSP":      (23651, "Surging Sparks",                  "B8"),
    "PRE":      (23821, "Prismatic Evolutions",            "B8"),
    "JTG":      (24073, "Journey Together",                "B8"),
    "MCD24":    (24163, "McDonalds 2024",                  "B8"),
    "DRI":      (24269, "Destined Rivals",                 "B8"),
    "BLK":      (24325, "Black Bolt",                      "B8"),
    "WHT":      (24326, "White Flare",                     "B8"),
    "SVE":      (24382, "Scarlet & Violet Energies",       "B8"),
    "PRIZEPACK":(22880, "Prize Pack Series",               "B8"),
    "MEG":      (24380, "Mega Evolution",                  "B9"),
    "PFL":      (24448, "Phantasmal Flames",               "B9"),
    "MEP":      (24451, "Mega Evolution Promos",           "B9"),
    "MEE":      (24461, "Mega Evolution Energies",         "B9"),
    "ASC":      (24541, "Ascended Heroes",                 "B9"),
    "POR":      (24587, "Perfect Order",                   "B9"),
    "CRI":      (24655, "Chaos Rising",                    "B9"),
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
    "Common": "common", "Uncommon": "uncommon", "Rare": "rare",
    "Holo Rare": "holo_rare", "Rare Holo": "holo_rare",
    "Rare Holo V": "holo_rare", "Rare Holo VMAX": "ultra_rare",
    "Rare Holo VSTAR": "ultra_rare", "Rare Holo EX": "ultra_rare",
    "Rare Holo GX": "ultra_rare", "Ultra Rare": "ultra_rare",
    "Double Rare": "ultra_rare", "Illustration Rare": "illustration_rare",
    "Special Illustration Rare": "special_illustration_rare",
    "Hyper Rare": "hyper_rare", "Shiny Rare": "shiny_rare",
    "Shiny Ultra Rare": "shiny_ultra_rare", "Rare Secret": "secret_rare",
    "Rare Rainbow": "hyper_rare", "Rare Shining": "holo_rare",
    "Rare Shiny": "shiny_rare", "Rare Shiny GX": "shiny_ultra_rare",
    "Rare Prism Star": "ultra_rare", "Amazing Rare": "ultra_rare",
    "Trainer Gallery Rare Holo": "holo_rare",
    "Trainer Gallery Ultra Rare": "ultra_rare",
    "Trainer Gallery Secret Rare": "secret_rare",
    "Classic Collection": "holo_rare", "ACE SPEC Rare": "ultra_rare",
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
    raise CommandError("Could not fetch USD/ZAR rate.")


def _zar_price(usd, rate):
    raw = Decimal(str(usd)) * rate * MARKUP
    cents = (raw * 2).quantize(Decimal("1"), rounding=ROUND_UP)
    return cents / 2


def _ext(extended_data, field_name):
    for item in extended_data:
        if item.get("name") == field_name:
            return item.get("value", "")
    return ""


def _parse_number(raw):
    """Strip '001/102' -> '1'. Return None if not a plain integer."""
    if not raw:
        return None
    raw = str(raw).split("/")[0].strip()
    try:
        return int(raw)
    except ValueError:
        return None  # skip SH1, SWSH001, DP50 etc


def _sync_group(set_code, group_id, set_name, era_code, rate, dry_run):
    created = skipped = no_price = non_card = 0

    try:
        r = requests.get(f"{TCGCSV_BASE}/{group_id}/products", headers=HEADERS, timeout=30)
        r.raise_for_status()
        products = r.json().get("results", [])
    except Exception as e:
        print(f"  [products] fetch failed: {e}")
        return dict(created=0, skipped=0, no_price=0, non_card=0)

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

    era = Era.objects.get(code=era_code)
    card_set, _ = CardSet.objects.get_or_create(
        code=set_code,
        defaults={"name": set_name, "era": era}
    )
    category, _ = Category.objects.get_or_create(name="Pokemon")

    # Get all existing productId+variant combos in one query
    existing = set(
        PokemonProduct.objects.filter(tcgcsv_product_id__isnull=False)
        .values_list("tcgcsv_product_id", "variant_override")
    )

    to_create = []

    for p in products:
        pid = p.get("productId")
        name = (p.get("name") or "").strip()
        image_url = p.get("imageUrl", "")
        ext = p.get("extendedData", [])

        number_raw = _ext(ext, "Number")
        rarity_raw = _ext(ext, "Rarity")

        card_number = _parse_number(number_raw)
        if card_number is None:
            non_card += 1
            continue

        # Get all price rows for this product (one per variant)
        product_prices = {sub: usd for (p_id, sub), usd in prices.items() if p_id == pid}
        if not product_prices:
            product_prices = {"": None}

        for sub, usd in product_prices.items():
            variant = SUBTYPE_MAP.get(sub, "N")
            rarity = RARITY_MAP.get(rarity_raw, "common")
            zar = _zar_price(usd, rate) if usd else None

            if usd is None:
                no_price += 1

            pb_id = f"{set_code}-{card_number}-{variant}"

            if (pid, variant) in existing:
                skipped += 1
                continue

            if dry_run:
                print(f"    [DRY] {pb_id} | {name} | {variant} | R{zar}")
                created += 1
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
                price=zar if zar is not None else 0,
                stock=0,
            ))

    if to_create and not dry_run:
        with transaction.atomic():
            result = PokemonProduct.objects.bulk_create(to_create, ignore_conflicts=True)
            created = len(result)

    return dict(created=created, skipped=skipped, no_price=no_price, non_card=non_card)


class Command(BaseCommand):
    help = "Sync cards from TCGCSV into Railway DB"

    def add_arguments(self, parser):
        parser.add_argument("--set-code", type=str)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--rate", type=float)
        parser.add_argument("--delay", type=float, default=0.1)

    def handle(self, *args, **options):
        set_filter = options.get("set_code")
        dry_run = options.get("dry_run", False)
        delay = options.get("delay", 0.1)

        self.stdout.write("Fetching USD/ZAR rate…")
        rate = _get_rate(options.get("rate"))
        self.stdout.write(f"1 USD = R{rate:.2f}\n")

        config = GROUP_CONFIG
        if set_filter:
            if set_filter not in config:
                raise CommandError(f"Unknown set code: {set_filter}")
            config = {set_filter: config[set_filter]}

        total = len(config)
        self.stdout.write(f"Processing {total} group(s)…")

        grand = dict(created=0, skipped=0, no_price=0, non_card=0)

        for i, (code, (gid, sname, era_code)) in enumerate(config.items(), 1):
            self.stdout.write(f"[{i}/{total}] {code} — {sname} (group {gid})")
            stats = _sync_group(code, gid, sname, era_code, rate, dry_run)
            self.stdout.write(
                f"  ✓ created={stats['created']}  skipped={stats['skipped']}"
                f"  no_price={stats['no_price']}  non_card={stats['non_card']}"
            )
            for k in grand:
                grand[k] += stats[k]
            if delay:
                time.sleep(delay)

        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(
            f"DONE  created={grand['created']}  skipped={grand['skipped']}"
            f"  no_price={grand['no_price']}  non_card={grand['non_card']}"
        )
        self.stdout.write(f"Net new cards in DB: {grand['created']}")
