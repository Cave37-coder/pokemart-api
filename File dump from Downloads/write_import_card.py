content = '''import requests
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import PokemonProduct, Category, PokemonType, Era, CardSet

RARITY_MAP = {
    "Common": "common",
    "Uncommon": "uncommon",
    "Rare": "rare",
    "Rare Holo": "holo_rare",
    "Rare Holo EX": "ultra_rare",
    "Rare Holo GX": "ultra_rare",
    "Rare Holo V": "ultra_rare",
    "Rare Holo VMAX": "ultra_rare",
    "Rare Holo VSTAR": "ultra_rare",
    "Rare Ultra": "ultra_rare",
    "Ultra Rare": "ultra_rare",
    "Double Rare": "ultra_rare",
    "Illustration Rare": "illustration_rare",
    "Special Illustration Rare": "special_illustration_rare",
    "Hyper Rare": "hyper_rare",
    "Mega Hyper Rare": "mega_hyper_rare",
    "Mega Attack Rare": "mega_attack_rare",
    "Rare Secret": "secret_rare",
    "Rare Rainbow": "secret_rare",
    "Rare Shiny": "secret_rare",
    "Rare Shiny GX": "secret_rare",
    "Radiant Rare": "ultra_rare",
    "Amazing Rare": "ultra_rare",
    "ACE SPEC Rare": "ace_spec",
    "Promo": "rare",
    "Rare ACE": "ultra_rare",
    "Rare BREAK": "ultra_rare",
    "Rare Prime": "ultra_rare",
    "Rare Prism Star": "ultra_rare",
    "LEGEND": "legendary",
    "Shining Rare": "shining",
    "Rare Holo Star": "gold_star",
}

ERA_MAP = {
    "base1": ("B1", "WotC Base Era"),
    "base2": ("B1", "WotC Base Era"),
    "base3": ("B1", "WotC Base Era"),
    "base4": ("B1", "WotC Base Era"),
    "base5": ("B1", "WotC Base Era"),
    "base6": ("B1", "WotC Base Era"),
    "gym1":  ("B1", "WotC Base Era"),
    "gym2":  ("B1", "WotC Base Era"),
    "neo1":  ("B1", "WotC Base Era"),
    "neo2":  ("B1", "WotC Base Era"),
    "neo3":  ("B1", "WotC Base Era"),
    "neo4":  ("B1", "WotC Base Era"),
    "ecard1":("B1", "WotC Base Era"),
    "ecard2":("B1", "WotC Base Era"),
    "ecard3":("B1", "WotC Base Era"),
}

def get_era_for_set(set_id, series):
    if set_id in ERA_MAP:
        return ERA_MAP[set_id]
    s = series.lower() if series else ""
    if "ex" in s:
        return ("B2", "EX Era")
    elif "diamond" in s or "pearl" in s or "platinum" in s or "heartgold" in s or "soulsilver" in s:
        return ("B3", "Diamond & Pearl Era")
    elif "black" in s or "white" in s:
        return ("B4", "Black & White Era")
    elif "xy" in s:
        return ("B5", "XY Era")
    elif "sun" in s or "moon" in s:
        return ("B6", "Sun & Moon Era")
    elif "sword" in s or "shield" in s:
        return ("B7", "Sword & Shield Era")
    elif "scarlet" in s or "violet" in s:
        return ("B8", "Scarlet & Violet Era")
    elif "mega" in s:
        return ("B9", "Mega Evolution Era")
    return ("PR", "Promo")

MEGA_ERA_SETS = {"me1", "me2", "me2pt5", "me03", "me04", "me05"}

SET_VARIANT_CONFIG = {
    "base1": {
        "print_runs": ["1ES", "SH", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "base2": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "base3": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "base4": {
        "print_runs": ["N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "base5": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "base6": {
        "print_runs": ["N"],
        "holo_suffix": "H",
        "reverse_type": "single",
        "rh_for_holos": True,
    },
    "gym1": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "gym2": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "neo1": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
        "shining_cards": list(range(105, 112)),
    },
    "neo2": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
    },
    "neo3": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
        "shining_cards": [65, 66],
    },
    "neo4": {
        "print_runs": ["1E", "N"],
        "holo_suffix": "H",
        "reverse_type": "none",
        "shining_cards": list(range(109, 114)),
    },
    "ecard1": {
        "print_runs": ["N"],
        "holo_suffix": "H",
        "reverse_type": "single",
    },
    "ecard2": {
        "print_runs": ["N"],
        "holo_suffix": "H",
        "reverse_type": "single",
        "crystal_cards": True,
    },
    "ecard3": {
        "print_runs": ["N"],
        "holo_suffix": "H",
        "reverse_type": "single",
        "crystal_cards": True,
    },
    "sv8pt5": {
        "print_runs": ["N"],
        "holo_suffix": "H",
        "reverse_type": "dual_ball",
        "ball_variants": ["PB", "MB"],
    },
    "me2pt5": {
        "print_runs": ["N"],
        "holo_suffix": "MH",
        "reverse_type": "dual_energy_ball",
        "trainer_reverse": "single",
        "ex_reverse": "none",
    },
    "DEFAULT": {
        "print_runs": ["N"],
        "holo_suffix": "H",
        "reverse_type": "single",
    },
    "DEFAULT_MEGA": {
        "print_runs": ["N"],
        "holo_suffix": "MH",
        "reverse_type": "single",
    },
}

def get_set_config(set_id):
    if set_id in SET_VARIANT_CONFIG:
        return SET_VARIANT_CONFIG[set_id]
    if set_id in MEGA_ERA_SETS:
        return SET_VARIANT_CONFIG["DEFAULT_MEGA"]
    return SET_VARIANT_CONFIG["DEFAULT"]

SINGLE_LISTING_RARITIES = {
    "ultra_rare", "secret_rare", "legendary",
    "illustration_rare", "special_illustration_rare",
    "hyper_rare", "mega_hyper_rare", "mega_attack_rare",
    "ace_spec", "gold_star", "shining",
}

ASC_BALL_MAP = {
    1: "PB", 2: "PB", 4: "PB", 5: "PB", 6: "PB", 7: "PB",
    8: "FB", 9: "FB",
    11: "LB", 12: "LB", 13: "LB", 14: "LB", 15: "LB",
}

def get_asc_ball(card_number, card_name):
    if "Team Rocket" in card_name or "Rocket" in card_name:
        return "R"
    return ASC_BALL_MAP.get(card_number, "PB")

def zar(usd):
    return round(usd * 18.5, 2) if usd else None

def get_japanese_name(pokedex_number):
    if not pokedex_number:
        return ""
    try:
        r = requests.get(
            f"https://pokeapi.co/api/v2/pokemon-species/{pokedex_number}/",
            timeout=5
        )
        if r.status_code == 200:
            names = r.json().get("names", [])
            for n in names:
                if n.get("language", {}).get("name") == "ja":
                    return n.get("name", "")
    except Exception:
        pass
    return ""

def is_single_listing(rarity, subtypes, card_number, config):
    if rarity in SINGLE_LISTING_RARITIES:
        return True
    if subtypes:
        subs_upper = " ".join(subtypes).upper()
        for blocked in ["POKEMON EX", "POKEMON-EX", "GX", "VMAX", "VSTAR", "V-UNION", "TERA"]:
            if blocked in subs_upper:
                return True
        if " V" in subs_upper or subs_upper.endswith(" V"):
            return True
    if "shining_cards" in config and card_number in config["shining_cards"]:
        return True
    return False

def get_best_price(tcg_prices):
    for pt in ["holofoil", "1stEditionHolofoil", "reverseHolofoil", "normal"]:
        if pt in tcg_prices and tcg_prices[pt].get("market"):
            return zar(tcg_prices[pt]["market"])
    return 0

def get_single_suffix(rarity, subtypes):
    subs_str = " ".join(subtypes or []).upper()
    if "VSTAR" in subs_str: return "VST"
    if "VMAX" in subs_str: return "VX"
    if "V-UNION" in subs_str: return "VU"
    if "VSTAR" in subs_str: return "VST"
    if " V" in subs_str or subs_str.endswith(" V"): return "V"
    if "GX" in subs_str: return "GX"
    if "EX" in subs_str: return "EX"
    if "MEGA" in subs_str: return "MEX"
    if "BREAK" in subs_str: return "BRK"
    if "LEGEND" in subs_str: return "LGD"
    if rarity == "gold_star": return "GS"
    if rarity == "shining": return "SHN"
    if rarity == "illustration_rare": return "IR"
    if rarity == "special_illustration_rare": return "SIR"
    if rarity == "hyper_rare": return "HR"
    if rarity == "mega_hyper_rare": return "MHR"
    if rarity == "mega_attack_rare": return "MAR"
    if rarity == "ace_spec": return "AS"
    if rarity in ("ultra_rare", "secret_rare"): return "UR"
    if rarity == "legendary": return "RA"
    return "SR"

def get_label(suffix):
    labels = {
        "N": "Normal", "1E": "1st Edition", "1ES": "1st Edition Shadowless",
        "SH": "Shadowless", "H": "Holo", "MH": "Mirror Holo",
        "RH": "Reverse Holo", "RH-H": "Holo Reverse Holo",
        "TRH": "Trainer Reverse Holo", "ERH": "Energy Reverse Holo",
        "ERH-H": "Energy Reverse Holo Holo",
        "RH-PB": "Poke Ball Reverse Holo", "RH-MB": "Master Ball Reverse Holo",
        "BRH-PB": "Poke Ball Reverse Holo", "BRH-MB": "Master Ball Reverse Holo",
        "BRH-FB": "Friend Ball Reverse Holo", "BRH-LB": "Love Ball Reverse Holo",
        "BRH-QB": "Quick Ball Reverse Holo", "BRH-DB": "Dusk Ball Reverse Holo",
        "BRH-R": "Team Rocket Reverse Holo",
        "1E-H": "1st Edition Holo", "1ES-H": "1st Edition Shadowless Holo",
        "SH-H": "Shadowless Holo", "1E-MH": "1st Edition Mirror Holo",
        "GS": "Gold Star", "SHN": "Shining", "EX": "Pokemon-ex",
        "GX": "Pokemon-GX", "V": "Pokemon V", "VX": "Pokemon VMAX",
        "VST": "Pokemon VSTAR", "VU": "V-UNION", "MEX": "Mega Evolution ex",
        "BRK": "BREAK Evolution", "LGD": "LEGEND",
        "IR": "Illustration Rare", "SIR": "Special Illustration Rare",
        "HR": "Hyper Rare", "MHR": "Mega Hyper Rare",
        "MAR": "Mega Attack Rare", "AS": "ACE SPEC",
        "UR": "Ultra Rare", "RA": "Legendary", "SR": "Secret Rare",
    }
    return labels.get(suffix, suffix)

def get_variants(rarity, subtypes, set_id, card_number, card_name, tcg_prices, config, is_trainer):
    variants = []
    reverse_type = config.get("reverse_type", "none")

    if is_single_listing(rarity, subtypes, card_number, config):
        price = get_best_price(tcg_prices)
        suffix = get_single_suffix(rarity, subtypes)
        variants.append({"suffix": suffix, "label": get_label(suffix), "price": price})
        return variants

    if rarity == "holo_rare":
        holo_suffix = config.get("holo_suffix", "H")
        holo_price = zar(tcg_prices.get("holofoil", {}).get("market"))
        fe_holo_price = zar(tcg_prices.get("1stEditionHolofoil", {}).get("market"))
        print_runs = config.get("print_runs", ["N"])
        for run in print_runs:
            if run == "1ES":
                suffix = f"1ES-{holo_suffix}"
                price = zar(tcg_prices.get("1stEditionHolofoil", {}).get("market")) or 0
            elif run == "SH":
                suffix = f"SH-{holo_suffix}"
                price = holo_price or 0
            elif run == "1E":
                suffix = f"1E-{holo_suffix}"
                price = fe_holo_price or holo_price or 0
            else:
                suffix = holo_suffix
                price = holo_price or 0
            variants.append({"suffix": suffix, "label": get_label(suffix), "price": price})
        if reverse_type == "single":
            rh_price = zar(tcg_prices.get("reverseHolofoil", {}).get("market"))
            variants.append({"suffix": "RH-H", "label": "Reverse Holo", "price": rh_price or 0})
        elif reverse_type == "dual_energy_ball" and not is_trainer:
            ball = get_asc_ball(card_number, card_name)
            variants.append({"suffix": "ERH-H", "label": "Energy Reverse Holo", "price": 0})
            variants.append({"suffix": f"BRH-{ball}-H", "label": f"{ball} Reverse Holo", "price": 0})
        return variants

    normal_price = zar(tcg_prices.get("normal", {}).get("market"))
    fe_price = zar(tcg_prices.get("1stEditionNormal", {}).get("market"))
    rh_price = zar(tcg_prices.get("reverseHolofoil", {}).get("market"))
    print_runs = config.get("print_runs", ["N"])
    for run in print_runs:
        if run == "1ES":
            suffix, price = "1ES", (zar(tcg_prices.get("1stEditionNormal", {}).get("market")) or 0)
        elif run == "SH":
            suffix, price = "SH", (normal_price or 0)
        elif run == "1E":
            suffix, price = "1E", (fe_price or normal_price or 0)
        else:
            suffix, price = "N", (normal_price or 0)
        variants.append({"suffix": suffix, "label": get_label(suffix), "price": price})

    if reverse_type == "single":
        variants.append({"suffix": "RH", "label": "Reverse Holo", "price": rh_price or 0})
    elif reverse_type == "dual_ball":
        variants.append({"suffix": "RH-PB", "label": "Poke Ball Reverse Holo", "price": rh_price or 0})
        variants.append({"suffix": "RH-MB", "label": "Master Ball Reverse Holo", "price": rh_price or 0})
    elif reverse_type == "dual_energy_ball":
        if is_trainer:
            variants.append({"suffix": "TRH", "label": "Trainer Reverse Holo", "price": 0})
        else:
            ball = get_asc_ball(card_number, card_name)
            variants.append({"suffix": "ERH", "label": "Energy Reverse Holo", "price": 0})
            variants.append({"suffix": f"BRH-{ball}", "label": f"{ball} Reverse Holo", "price": 0})

    return variants


class Command(BaseCommand):
    help = "Import a Pokemon card with full variant support"

    def add_arguments(self, parser):
        parser.add_argument("card_id", type=str)
        parser.add_argument("--price", type=float, default=0.0)
        parser.add_argument("--stock", type=int, default=1)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        card_id = options["card_id"]
        manual_price = options["price"]
        stock = options["stock"]
        overwrite = options["overwrite"]

        self.stdout.write(f"Fetching card {card_id}...")

        headers = {}
        if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
            headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY

        response = requests.get(
            f"https://api.pokemontcg.io/v2/cards/{card_id}",
            headers=headers
        )
        if response.status_code != 200:
            self.stderr.write(f"Error {response.status_code} fetching {card_id}")
            return

        data = response.json().get("data", {})

        name = data.get("name", "")
        rarity_raw = data.get("rarity", "Common")
        rarity = RARITY_MAP.get(rarity_raw, "common")
        subs = data.get("subtypes", [])
        supertype = data.get("supertype", "")
        artist = data.get("artist", "")
        hp_raw = data.get("hp", None)
        hp = int(hp_raw) if hp_raw and str(hp_raw).isdigit() else None
        number = data.get("number", "0")
        national_pokedex = data.get("nationalPokedexNumbers", [None])[0]
        flavour_text = data.get("flavorText", "")
        image_url = data.get("images", {}).get("large", "")
        image_small_url = data.get("images", {}).get("small", "")

        weaknesses = data.get("weaknesses", [])
        weakness_type = weaknesses[0].get("type", "") if weaknesses else ""
        weakness_value = weaknesses[0].get("value", "") if weaknesses else ""

        resistances = data.get("resistances", [])
        resistance_type = resistances[0].get("type", "") if resistances else ""
        resistance_value = resistances[0].get("value", "") if resistances else ""

        retreat = data.get("retreatCost", [])
        retreat_cost = len(retreat) if retreat else None

        abilities = data.get("abilities", [])
        ability_name = abilities[0].get("name", "") if abilities else ""
        ability_type = abilities[0].get("type", "") if abilities else ""
        ability_text = abilities[0].get("text", "") if abilities else ""

        attacks = data.get("attacks", [])
        atk1 = attacks[0] if len(attacks) > 0 else {}
        atk2 = attacks[1] if len(attacks) > 1 else {}
        attack_1_name = atk1.get("name", "")
        attack_1_damage = atk1.get("damage", "")
        attack_1_text = atk1.get("text", "")
        attack_2_name = atk2.get("name", "")
        attack_2_damage = atk2.get("damage", "")
        attack_2_text = atk2.get("text", "")

        if not flavour_text and attack_1_text:
            flavour_text = attack_1_text

        tcgplayer_url = data.get("tcgplayer", {}).get("url", "")
        tcgplayer_id = tcgplayer_url.split("/")[-1] if tcgplayer_url else card_id
        tcg_prices = data.get("tcgplayer", {}).get("prices", {})

        set_data = data.get("set", {})
        set_id = set_data.get("id", "")
        set_name = set_data.get("name", "")
        set_code = set_data.get("ptcgoCode", set_id[:6].upper())
        series = set_data.get("series", "")
        symbol_url = set_data.get("images", {}).get("symbol", "")
        logo_url = set_data.get("images", {}).get("logo", "")
        total_cards = set_data.get("total", 0)
        release_date_raw = set_data.get("releaseDate", "")
        try:
            release_date = datetime.strptime(release_date_raw, "%Y/%m/%d").date() if release_date_raw else None
        except ValueError:
            release_date = None

        era_code, era_name = get_era_for_set(set_id, series)
        era, _ = Era.objects.get_or_create(code=era_code, defaults={"name": era_name})

        card_set, cs_created = CardSet.objects.get_or_create(
            code=set_code,
            defaults={
                "name": set_name, "era": era,
                "symbol_url": symbol_url, "logo_url": logo_url,
                "total_cards": total_cards, "release_date": release_date,
            }
        )
        if not cs_created and not card_set.symbol_url and symbol_url:
            card_set.symbol_url = symbol_url
            card_set.logo_url = logo_url
            card_set.total_cards = total_cards
            card_set.release_date = release_date
            card_set.save()

        category, _ = Category.objects.get_or_create(
            slug="cards", defaults={"name": "Cards"}
        )
        pokemon_types = []
        for t in data.get("types", []):
            pt, _ = PokemonType.objects.get_or_create(name=t)
            pokemon_types.append(pt)

        try:
            card_number = int("".join(filter(str.isdigit, number))) or 1
        except Exception:
            card_number = 1
        if not national_pokedex:
            national_pokedex = card_number

        name_japanese = ""
        if data.get("nationalPokedexNumbers"):
            name_japanese = get_japanese_name(national_pokedex)

        description = flavour_text if flavour_text else f"{rarity_raw} card from {set_name}"

        config = get_set_config(set_id)
        is_trainer = supertype.lower() in ("trainer", "energy")

        shining_cards = config.get("shining_cards", [])
        if card_number in shining_cards:
            rarity = "shining"

        variants = get_variants(
            rarity=rarity,
            subtypes=subs,
            set_id=set_id,
            card_number=card_number,
            card_name=name,
            tcg_prices=tcg_prices,
            config=config,
            is_trainer=is_trainer,
        )

        era_code_str = card_set.era.code if card_set.era else "XX"
        pokedex_str = str(national_pokedex).zfill(3)
        card_num_str = str(card_number).zfill(3)

        created_count = 0
        skipped_count = 0

        for variant in variants:
            suffix = variant["suffix"]
            label = variant["label"]
            price = manual_price if manual_price > 0 else variant["price"]

            pb_id = f"PB-{era_code_str}-{set_code}-{pokedex_str}-{suffix}-{card_num_str}"

            existing = PokemonProduct.objects.filter(pb_id=pb_id).first()
            if existing:
                if overwrite:
                    self.stdout.write(f"  Overwriting: {pb_id}")
                    existing.delete()
                else:
                    self.stdout.write(f"  Skipping: {pb_id}")
                    skipped_count += 1
                    continue

            display_name = f"{name} ({label})" if len(variants) > 1 else name

            product = PokemonProduct(
                pb_id=pb_id,
                name=display_name,
                name_japanese=name_japanese,
                category=category,
                card_set=card_set,
                rarity=rarity,
                pokedex_number=national_pokedex,
                card_number=card_number,
                variant_override=suffix,
                supertype=supertype,
                card_subtypes=", ".join(subs),
                hp=hp,
                artist=artist,
                weakness_type=weakness_type,
                weakness_value=weakness_value,
                resistance_type=resistance_type,
                resistance_value=resistance_value,
                retreat_cost=retreat_cost,
                ability_name=ability_name,
                ability_type=ability_type,
                ability_text=ability_text,
                attack_1_name=attack_1_name,
                attack_1_damage=attack_1_damage,
                attack_1_text=attack_1_text,
                attack_2_name=attack_2_name,
                attack_2_damage=attack_2_damage,
                attack_2_text=attack_2_text,
                flavour_text=flavour_text,
                description=f"{label} - {description}",
                image_url=image_url,
                image_small_url=image_small_url,
                price=price if price > 0 else 0,
                price_normal=zar(tcg_prices.get("normal", {}).get("market")),
                price_holo=zar(tcg_prices.get("holofoil", {}).get("market")),
                price_reverse_holo=zar(tcg_prices.get("reverseHolofoil", {}).get("market")),
                price_first_edition=zar(tcg_prices.get("1stEditionHolofoil", {}).get("market")),
                stock=stock,
                tcgplayer_id=tcgplayer_id,
            )
            product.save()

            if pokemon_types:
                product.pokemon_types.set(pokemon_types)

            self.stdout.write(self.style.SUCCESS(
                f"  [{suffix}] {pb_id} - {name} @ R{price}"
            ))
            created_count += 1

        self.stdout.write(f"Done: {name} | Created: {created_count} | Skipped: {skipped_count}")
        if ability_name:
            self.stdout.write(f"  Ability: [{ability_type}] {ability_name}")
        self.stdout.write(f"  Attacks: {attack_1_name} / {attack_2_name}")
        if name_japanese:
            self.stdout.write(f"  Japanese: {name_japanese}")
'''

with open("products/management/commands/import_card.py", "w", encoding="utf-8") as f:
    f.write(content)
print("import_card.py written!")