"""
enrich_only - PokeBulk SA
Enriches existing DB records with data from pokemontcg.io
NEVER creates, deletes or touches price/stock
Only updates: images, types, attacks, abilities, hp, artist etc.

Usage:
  python manage.py enrich_only ASC
  python manage.py enrich_only ASC --dry-run
  python manage.py enrich_only ALL  (runs all sets)
"""

import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from products.models import PokemonProduct, CardSet, PokemonType

# Map our set codes to pokemontcg.io set IDs
SET_ID_MAP = {
    # Base Era
    'BS':       'base1',
    'BS2':      'base4',
    'BSS':      'basep',
    'FO':       'base3',
    'JU':       'base2',
    'TR':       'base5',
    'G1':       'gym1',
    'G2':       'gym2',
    'N1':       'neo1',
    'N2':       'neo2',
    'N3':       'neo3',
    'N4':       'neo4',
    'LC':       'base6',
    'SI1':      'si1',
    'PR-WB':    'basep',
    # EX Era
    'EX':       'ecard1',
    'AQ':       'ecard2',
    'SK':       'ecard3',
    'RS':       'ex1',
    'SS':       'ex2',
    'DR':       'ex3',
    'MA':       'ex4',
    'HL':       'ex5',
    'RG':       'ex6',
    'TRR':      'ex7',
    'DX':       'ex8',
    'EM':       'ex9',
    'UF':       'ex10',
    'DS':       'ex11',
    'LM':       'ex12',
    'HP':       'ex13',
    'CG':       'ex14',
    'DF':       'ex15',
    'PK':       'ex16',
    # DP Era
    'DP':       'dp1',
    'MT':       'dp2',
    'SW':       'dp3',
    'GE':       'dp4',
    'MD':       'dp5',
    'LA':       'dp6',
    'SF':       'dp7',
    'PL':       'pl1',
    'RR':       'pl2',
    'SV':       'pl3',
    'AR':       'pl4',
    'HS':       'hgss1',
    'UL':       'hgss2',
    'UD':       'hgss3',
    'TM':       'hgss4',
    'CoL':      'col1',
    'PR-HS':    'hsp',
    'PR-DP':    'dpp',
    # BW Era
    'BLW':      'bw1',
    'EPO':      'bw2',
    'NVI':      'bw3',
    'NXD':      'bw4',
    'DEX':      'bw5',
    'DRX':      'bw6',
    'DRV':      'dv1',
    'BCR':      'bw7',
    'PLS':      'bw8',
    'PLF':      'bw9',
    'PLB':      'bw10',
    'LTR':      'bw11',
    'LTRRC':    'bw11',
    'PR-BLW':   'bwp',
    'MCD11':    'mcd11',
    'MCD12':    'mcd12',
    # XY Era
    'KSS':      'xy0',
    'XY':       'xy1',
    'FLF':      'xy2',
    'FFI':      'xy3',
    'PHF':      'xy4',
    'PRC':      'xy5',
    'DCR':      'dc1',
    'ROS':      'xy6',
    'AOR':      'xy7',
    'BKT':      'xy8',
    'BKP':      'xy9',
    'GEN':      'g1',
    'GENRC':    'g1',
    'FCO':      'xy10',
    'STS':      'xy11',
    'EVO':      'xy12',
    'PR-XY':    'xyp',
    'MCD14':    'mcd14',
    'MCD15':    'mcd15',
    'MCD16':    'mcd16',
    # SM Era
    'SM01':     'sm1',
    'SM02':     'sm2',
    'SM03':     'sm3',
    'SHL':      'sm35',
    'SM04':     'sm4',
    'SM05':     'sm5',
    'SM06':     'sm6',
    'CES':      'sm7',
    'DRM':      'sm75',
    'SM8':      'sm8',
    'SM9':      'sm9',
    'DEP':      'det1',
    'SM10':     'sm10',
    'SM11':     'sm11',
    'HIF':      'sm115',
    'HIFSV':    'sma',
    'SM12':     'sm12',
    'PR-SM':    'smp',
    'MCD17':    'mcd17',
    'MCD18':    'mcd18',
    'MCD19':    'mcd19',
    # SwSh Era
    'SWSH01':   'swsh1',
    'SWSH02':   'swsh2',
    'SWSH03':   'swsh3',
    'CHP':      'swsh35',
    'SWSH04':   'swsh4',
    'SHF':      'swsh45',
    'SHFSV':    'swsh45sv',
    'SWSH05':   'swsh5',
    'MCD21':    'mcd21',
    'SWSH06':   'swsh6',
    'SWSH07':   'swsh7',
    'CLB':      'cel25',
    'CCC':      'cel25c',
    'SWSH08':   'swsh8',
    'SWSH09':   'swsh9',
    'BST':      'swsh9tg',
    'SWSH10':   'swsh10',
    'PGO':      'pgo',
    'ASRTG':    'swsh10tg',
    'SWSH11':   'swsh11',
    'LORTG':    'swsh11tg',
    'SWSH12':   'swsh12',
    'ST':       'swsh12tg',
    'CRZ':      'swsh12pt5',
    'CRZGG':    'swsh12pt5gg',
    'TOT22':    'poptb',
    'MCD22':    'mcd22',
    'PR-SWSH':  'swshp',
    # SV Era
    'SVP':      'svp',
    'SVI':      'sv1',
    'PRIZEPACK':'svp',
    'PAL':      'sv2',
    'OBF':      'sv3',
    'MEW':      'sv3pt5',
    'TOT23':    'poptb',
    'PAR':      'sv4',
    'MCD23':    'mcd23',
    'TCGCL':    'mcd23',
    'PAF':      'sv4pt5',
    'TEF':      'sv5',
    'TWM':      'sv6',
    'SFA':      'sv6pt5',
    'SCR':      'sv7',
    'TOT24':    'poptb',
    'SSP':      'sv8',
    'PRE':      'sv8pt5',
    'JTG':      'sv9',
    'MCD24':    'mcd24',
    'DRI':      'sv10',
    'BLK':      'zsv10pt5',
    'WHT':      'rsv10pt5',
    'SVE':      'sve',
    # ME Era
    'MEG':      'me1',
    'PFL':      'me2',
    'MEP':      'mep',
    'MEE':      'mee',
    'ASC':      'me2pt5',
    'POR':      'me3',
    'CRI':      'me4',
}

def fetch_cards_from_api(ptcgio_set_id, headers):
    """Fetch all cards for a set from pokemontcg.io"""
    all_cards = []
    page = 1
    while True:
        url = f"https://api.pokemontcg.io/v2/cards?q=set.id:{ptcgio_set_id}&pageSize=250&page={page}&orderBy=number"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 429:
            print(f"  Rate limited, waiting 10s...")
            time.sleep(10)
            continue
        if r.status_code != 200:
            print(f"  API error: {r.status_code}")
            break
        data = r.json()
        cards = data.get("data", [])
        all_cards.extend(cards)
        total = data.get("totalCount", 0)
        if len(all_cards) >= total or not cards:
            break
        page += 1
        time.sleep(0.3)
    return all_cards

def parse_card_number(raw):
    """Extract numeric part from card number"""
    import re
    if not raw:
        return None
    raw = str(raw).split("/")[0].strip()
    try:
        return int(raw)
    except ValueError:
        match = re.match(r'^[A-Za-z]+(\d+)$', raw)
        if match:
            return int(match.group(1))
        return None

def enrich_set(set_code, ptcgio_set_id, headers, dry_run=False, stdout=None):
    def log(msg):
        if stdout:
            stdout.write(msg)
        else:
            print(msg)

    log(f"  Fetching cards from pokemontcg.io ({ptcgio_set_id})...")
    api_cards = fetch_cards_from_api(ptcgio_set_id, headers)
    log(f"  Got {len(api_cards)} cards from API")

    if not api_cards:
        log(f"  No cards returned — skipping")
        return 0, 0

    # Build lookup: card_number -> api card data
    api_lookup = {}
    for card in api_cards:
        num = parse_card_number(card.get("number", ""))
        if num is not None:
            if num not in api_lookup:
                api_lookup[num] = card

    # Get all DB records for this set
    db_records = list(PokemonProduct.objects.filter(
        card_set__code=set_code
    ).prefetch_related('pokemon_types'))

    log(f"  DB records: {len(db_records)}")

    updated = 0
    not_found = 0
    to_update = []

    for product in db_records:
        card_num = product.card_number
        if card_num not in api_lookup:
            not_found += 1
            continue

        card = api_lookup[card_num]

        # Extract enrichment data
        image_url       = card.get("images", {}).get("large", "") or ""
        image_small_url = card.get("images", {}).get("small", "") or ""
        supertype       = card.get("supertype", "") or ""
        card_subtypes   = ", ".join(card.get("subtypes", [])) or ""
        hp_raw          = card.get("hp", None)
        hp              = int(hp_raw) if hp_raw and str(hp_raw).isdigit() else None
        artist          = card.get("artist", "") or ""
        legalities      = card.get("legalities", {})
        legal_standard  = True if legalities.get("standard","").lower()=="legal" else (False if legalities.get("standard") else None)
        legal_expanded  = True if legalities.get("expanded","").lower()=="legal" else (False if legalities.get("expanded") else None)
        legal_unlimited = legalities.get("unlimited","").lower()=="legal"
        flavour_text    = card.get("flavorText", "") or ""
        pokedex_numbers = card.get("nationalPokedexNumbers", [])
        pokedex_number  = pokedex_numbers[0] if pokedex_numbers else None

        weaknesses      = card.get("weaknesses", [])
        weakness_type   = weaknesses[0].get("type", "") if weaknesses else ""
        weakness_value  = weaknesses[0].get("value", "") if weaknesses else ""

        resistances     = card.get("resistances", [])
        resistance_type = resistances[0].get("type", "") if resistances else ""
        resistance_value= resistances[0].get("value", "") if resistances else ""

        retreat         = card.get("retreatCost", [])
        retreat_cost    = len(retreat) if retreat else None

        abilities       = card.get("abilities", [])
        ability_name    = abilities[0].get("name", "") if abilities else ""
        ability_type    = abilities[0].get("type", "") if abilities else ""
        ability_text    = abilities[0].get("text", "") if abilities else ""

        attacks         = card.get("attacks", [])
        atk1            = attacks[0] if len(attacks) > 0 else {}
        atk2            = attacks[1] if len(attacks) > 1 else {}
        attack_1_name   = atk1.get("name", "") or ""
        attack_1_damage = atk1.get("damage", "") or ""
        attack_1_text   = atk1.get("text", "") or ""
        attack_2_name   = atk2.get("name", "") or ""
        attack_2_damage = atk2.get("damage", "") or ""
        attack_2_text   = atk2.get("text", "") or ""

        # pokemontcg.io card ID
        tcgplayer_id    = card.get("id", "") or ""

        # Pokemon types
        type_names = card.get("types", [])

        if dry_run:
            log(f"    [DRY] #{card_num} {product.variant_override} {product.name[:25]} -> image={'YES' if image_url else 'NO'} types={type_names}")
            updated += 1
            continue

        # Update fields
        product.image_url        = image_url
        product.image_small_url  = image_small_url
        product.supertype        = supertype
        product.card_subtypes    = card_subtypes
        product.hp               = hp
        product.artist           = artist
        product.flavour_text     = flavour_text
        product.pokedex_number   = pokedex_number
        product.legal_standard   = legal_standard
        product.legal_expanded   = legal_expanded
        product.legal_unlimited  = legal_unlimited
        product.weakness_type    = weakness_type
        product.weakness_value   = weakness_value
        product.resistance_type  = resistance_type
        product.resistance_value = resistance_value
        product.retreat_cost     = retreat_cost
        product.ability_name     = ability_name
        product.ability_type     = ability_type
        product.ability_text     = ability_text
        product.attack_1_name    = attack_1_name
        product.attack_1_damage  = attack_1_damage
        product.attack_1_text    = attack_1_text
        product.attack_2_name    = attack_2_name
        product.attack_2_damage  = attack_2_damage
        product.attack_2_text    = attack_2_text
        product.tcgplayer_id     = tcgplayer_id

        to_update.append(product)

        # Update pokemon types
        if type_names:
            types = []
            for t in type_names:
                pt, _ = PokemonType.objects.get_or_create(name=t)
                types.append(pt)
            product.pokemon_types.set(types)

        updated += 1

    # Bulk update all fields at once
    if to_update and not dry_run:
        FIELDS = [
            'image_url', 'image_small_url', 'supertype', 'card_subtypes',
            'hp', 'artist', 'flavour_text', 'pokedex_number',
              'legal_standard', 'legal_expanded', 'legal_unlimited',
            'weakness_type', 'weakness_value', 'resistance_type', 'resistance_value',
            'retreat_cost', 'ability_name', 'ability_type', 'ability_text',
            'attack_1_name', 'attack_1_damage', 'attack_1_text',
            'attack_2_name', 'attack_2_damage', 'attack_2_text',
            'tcgplayer_id',
        ]
        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, FIELDS, batch_size=500)

    log(f"  Updated: {updated} | Not found in API: {not_found}")
    # Propagate legality from any found variant to all variants of same card/set
    from django.db.models import Q
    cards_with_legality = PokemonProduct.objects.filter(
        card_set__code=set_code,
        legal_standard__isnull=False
    ).values('card_number', 'legal_standard', 'legal_expanded', 'legal_unlimited').distinct()
    
    propagated = 0
    for card in cards_with_legality:
        updated_count = PokemonProduct.objects.filter(
            card_set__code=set_code,
            card_number=card['card_number'],
          legal_standard__isnull=True
        ).update(
          legal_standard=card['legal_standard'],
          legal_expanded=card['legal_expanded'],
          legal_unlimited=card['legal_unlimited'],
        )
        propagated += updated_count
    
    if propagated:
        print(f"  Propagated legality to {propagated} variants")

    return updated, not_found


class Command(BaseCommand):
    help = "Enrich existing DB records with pokemontcg.io data — never creates or deletes"

    def add_arguments(self, parser):
        parser.add_argument("set_code", type=str, help="Set code e.g. ASC, PRE, BLK, WHT or ALL")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without saving")

    def handle(self, *args, **options):
        set_code = options["set_code"].upper()
        dry_run = options.get("dry_run", False)

        headers = {}
        if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
            headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY

        if set_code == "ALL":
            sets_to_run = list(CardSet.objects.values_list("code", flat=True))
        else:
            sets_to_run = [set_code]

        total_updated = 0
        total_not_found = 0

        for code in sets_to_run:
            ptcgio_id = SET_ID_MAP.get(code)
            if not ptcgio_id:
                self.stdout.write(f"[{code}] No pokemontcg.io mapping — skipping")
                continue

            self.stdout.write(f"\n[{code}] Enriching from pokemontcg.io set '{ptcgio_id}'...")
            if dry_run:
                self.stdout.write("  DRY RUN — no changes will be saved")

            updated, not_found = enrich_set(
                set_code=code,
                ptcgio_set_id=ptcgio_id,
                headers=headers,
                dry_run=dry_run,
                stdout=self.stdout,
            )
            total_updated += updated
            total_not_found += not_found
            time.sleep(0.5)

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"DONE")
        self.stdout.write(f"  Total updated:   {total_updated}")
        self.stdout.write(f"  Total not found: {total_not_found}")
        if dry_run:
            self.stdout.write("  (DRY RUN — nothing was saved)")
