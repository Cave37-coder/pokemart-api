import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import PokemonProduct, Category, PokemonType, Era, CardSet

RARITY_MAP = {
    "Common": "common", "Uncommon": "uncommon", "Rare": "rare",
    "Rare Holo": "holo_rare", "Rare Ultra": "ultra_rare",
    "Rare Secret": "secret_rare", "Rare Rainbow": "legendary",
    "Rare Holo EX": "ultra_rare", "Rare Holo GX": "ultra_rare",
    "Rare Holo V": "ultra_rare", "Rare Holo VMAX": "ultra_rare",
    "Rare Holo VSTAR": "ultra_rare", "Illustration Rare": "ultra_rare",
    "Special Illustration Rare": "secret_rare", "Hyper Rare": "secret_rare",
    "Amazing Rare": "ultra_rare", "Promo": "rare",
    "Rare Shiny": "secret_rare", "Rare Shiny GX": "secret_rare",
    "Radiant Rare": "ultra_rare", "ACE SPEC Rare": "secret_rare",
    "Double Rare": "ultra_rare", "Ultra Rare": "ultra_rare",
    "Rare ACE": "ultra_rare", "Rare BREAK": "ultra_rare",
    "Rare Prime": "ultra_rare", "Rare Prism Star": "ultra_rare",
    "LEGEND": "legendary",
}

VARIANT_CODES = {
    "common": "S", "uncommon": "S", "rare": "S",
    "holo_rare": "H", "ultra_rare": "FA",
    "secret_rare": "SR", "legendary": "RA",
}

ERA_MAP = {
    "base1": ("B1", "WotC Base Era"), "base2": ("B1", "WotC Base Era"),
    "base3": ("B1", "WotC Base Era"), "base4": ("B1", "WotC Base Era"),
    "base5": ("B1", "WotC Base Era"), "base6": ("B1", "WotC Base Era"),
    "gym1": ("B1", "WotC Base Era"), "gym2": ("B1", "WotC Base Era"),
    "neo1": ("B1", "WotC Base Era"), "neo2": ("B1", "WotC Base Era"),
    "neo3": ("B1", "WotC Base Era"), "neo4": ("B1", "WotC Base Era"),
    "ecard1": ("B1", "WotC Base Era"), "ecard2": ("B1", "WotC Base Era"),
    "ecard3": ("B1", "WotC Base Era"),
}


def get_era_for_set(set_id, series):
    if set_id in ERA_MAP:
        return ERA_MAP[set_id]
    s = series.lower() if series else ""
    if "ex" in s:
        return ("B2", "EX Era")
    elif "diamond" in s or "pearl" in s or "platinum" in s:
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
    return ("PR", "Promo")


def get_variant(subs, rarity_raw):
    if not subs:
        return ""
    st = " ".join(subs).upper()
    if "VSTAR" in st: return "VT"
    if "VMAX" in st: return "VX"
    if "V-UNION" in st: return "VU"
    if st.endswith(" V") or " V " in st: return "V"
    if "GX" in st: return "GX"
    if "EX" in st: return "EX"
    if "MEGA" in st: return "M"
    if "BREAK" in st: return "BRK"
    if "LEGEND" in st: return "LGD"
    if "PRIME" in st: return "PRM"
    if "TAG TEAM" in st: return "TT"
    if "RADIANT" in rarity_raw.upper(): return "RAD"
    if "AMAZING" in rarity_raw.upper(): return "AMZ"
    return ""


def zar(usd):
    return round(usd * 18.5, 2) if usd else None


class Command(BaseCommand):
    help = "Import a Pokemon card by TCG API ID"

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

        self.stdout.write(f"Fetching card {card_id} from Pokemon TCG API...")

        headers = {}
        if settings.POKEMONTCG_API_KEY:
            headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY

        response = requests.get(
            f"https://api.pokemontcg.io/v2/cards/{card_id}",
            headers=headers
        )

        if response.status_code != 200:
            self.stderr.write(f"Error: {response.status_code}")
            return

        data = response.json().get("data", {})

        name = data.get("name", "")
        rarity_raw = data.get("rarity", "Common")
        rarity = RARITY_MAP.get(rarity_raw, "common")
        subs = data.get("subtypes", [])
        supertype = data.get("supertype", "")
        variant_override = get_variant(subs, rarity_raw)
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
        tcgplayer_id = tcgplayer_url.split("/")[-1] if tcgplayer_url else ""
        tcg_prices = data.get("tcgplayer", {}).get("prices", {})

        price_normal = zar(tcg_prices.get("normal", {}).get("market"))
        price_holo = zar(tcg_prices.get("holofoil", {}).get("market"))
        price_reverse_holo = zar(tcg_prices.get("reverseHolofoil", {}).get("market"))
        price_first_edition = zar(tcg_prices.get("1stEditionHolofoil", {}).get("market"))

        price = manual_price
        if price == 0.0:
            for pt in ["holofoil", "reverseHolofoil", "normal", "1stEditionHolofoil"]:
                if pt in tcg_prices:
                    market = tcg_prices[pt].get("market")
                    if market:
                        price = round(market * 18.5, 2)
                        self.stdout.write(f"Price from TCGplayer: ${market} USD = R{price} ZAR")
                        break

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

        card_set, _ = CardSet.objects.get_or_create(
            code=set_code,
            defaults={
                "name": set_name, "era": era,
                "symbol_url": symbol_url, "logo_url": logo_url,
                "total_cards": total_cards, "release_date": release_date,
            }
        )

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

        existing = PokemonProduct.objects.filter(
            card_set=card_set, card_number=card_number, rarity=rarity
        ).first()

        if existing:
            if overwrite:
                self.stdout.write(f"Overwriting: {existing.pb_id}")
                existing.delete()
            else:
                self.stdout.write(self.style.WARNING(f"Card already exists: {existing.pb_id}"))
                raise SystemExit(0)

        description = flavour_text if flavour_text else f"{rarity_raw} card from {set_name}"

        product = PokemonProduct(
            name=name, category=category, card_set=card_set,
            rarity=rarity, pokedex_number=national_pokedex,
            card_number=card_number, variant_override=variant_override,
            supertype=supertype, card_subtypes=", ".join(subs),
            hp=hp, artist=artist,
            weakness_type=weakness_type, weakness_value=weakness_value,
            resistance_type=resistance_type, resistance_value=resistance_value,
            retreat_cost=retreat_cost,
            attack_1_name=attack_1_name, attack_1_damage=attack_1_damage,
            attack_1_text=attack_1_text, attack_2_name=attack_2_name,
            attack_2_damage=attack_2_damage, attack_2_text=attack_2_text,
            flavour_text=flavour_text, description=description,
            image_url=image_url, image_small_url=image_small_url,
            price=price if price > 0 else 0,
            price_normal=price_normal, price_holo=price_holo,
            price_reverse_holo=price_reverse_holo,
            price_first_edition=price_first_edition,
            stock=stock, tcgplayer_id=tcgplayer_id,
        )
        product.save()

        if pokemon_types:
            product.pokemon_types.set(pokemon_types)

        self.stdout.write(self.style.SUCCESS(
            f"Imported: {product.pb_id} - {product.name} @ R{product.price}"
        ))
        self.stdout.write(f"SKU: {product.sku} | Artist: {artist} | HP: {hp}")
        self.stdout.write(f"Attacks: {attack_1_name} / {attack_2_name}")
        self.stdout.write(f"Flavour: {flavour_text[:80]}" if flavour_text else "Flavour: none")
