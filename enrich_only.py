"""
enrich_only.py - PokeBulk SA
Verifies pokemontcg.io mapping before enriching.
NEVER touches price, stock, variant, card_number.

Usage:
  python manage.py enrich_only ALL --verify-only
  python manage.py enrich_only ALL
  python manage.py enrich_only ASC
"""
import requests, time, re
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from products.models import PokemonProduct, CardSet, PokemonType

SET_ID_MAP = {
    'BS':'base1','BS2':'base4','FO':'base3','JU':'base2','TR':'base5',
    'G1':'gym1','G2':'gym2','N1':'neo1','N2':'neo2','N3':'neo3','N4':'neo4',
    'LC':'base6','SI1':'si1',
    'EX':'ecard1','AQ':'ecard2','SK':'ecard3',
    'RS':'ex1','SS':'ex2','DR':'ex3','MA':'ex4','HL':'ex5','RG':'ex6',
    'TRR':'ex7','EM':'ex9','UF':'ex10','DS':'ex11','LM':'ex12',
    'HP':'ex13','CG':'ex14','DF':'ex15','PK':'ex16',
    'DP':'dp1','MT':'dp2','SW':'dp3','GE':'dp4','MD':'dp5','LA':'dp6',
    'SF':'dp7','PL':'pl1','RR':'pl2','SV':'pl3','AR':'pl4',
    'HS':'hgss1','UL':'hgss2','UD':'hgss3','TM':'hgss4','CL':'col1',
    'BLW':'bw1','EPO':'bw2','NVI':'bw3','NXD':'bw4','DEX':'bw5',
    'DRX':'bw6','DRV':'dv1','BCR':'bw7','PLS':'bw8','PLF':'bw9',
    'PLB':'bw10','LTR':'bw11',
    'KSS':'xy0','XY':'xy1','FLF':'xy2','FFI':'xy3','PHF':'xy4',
    'PRC':'xy5','DCR':'dc1','ROS':'xy6','AOR':'xy7','BKT':'xy8',
    'BKP':'xy9','GEN':'g1','FCO':'xy10','STS':'xy11','EVO':'xy12',
    'SUM':'sm1','GRI':'sm2','BUS':'sm3','SLG':'sm35','CIN':'sm4',
    'UPR':'sm5','FLI':'sm6','CES':'sm7','DRM':'sm75','LOT':'sm8',
    'TEU':'sm9','UNB':'sm10','UNM':'sm11','HIF':'sm115','CEC':'sm12',
    'SWSH01':'swsh1','SWSH02':'swsh2','SWSH03':'swsh3','CPA':'swsh35',
    'SWSH04':'swsh4','SHF':'swsh45','SWSH05':'swsh5','SWSH06':'swsh6',
    'SWSH07':'swsh7','CLB':'cel25','SWSH08':'swsh8','SWSH09':'swsh9',
    'BST':'swsh9tg','SWSH10':'swsh10','PGO':'pgo','SWSH11':'swsh11',
    'SWSH12':'swsh12','CRZ':'swsh12pt5',
    'SVI':'sv1','PAL':'sv2','OBF':'sv3','MEW':'sv3pt5','PAR':'sv4',
    'PAF':'sv4pt5','TEF':'sv5','TWM':'sv6','SFA':'sv6pt5','SCR':'sv7',
    'SSP':'sv8','PRE':'sv8pt5','JTG':'sv9','DRI':'sv10',
    # MEG era - not yet on pokemontcg.io, commented out
    # 'MEG':'me1','PFL':'me2','ASC':'me2pt5','POR':'me3','CRI':'me4',
}

def fetch_cards(ptcgio_id, headers):
    all_cards, page = [], 1
    while True:
        r = requests.get(
            f"https://api.pokemontcg.io/v2/cards?q=set.id:{ptcgio_id}&pageSize=250&page={page}&orderBy=number",
            headers=headers, timeout=30)
        if r.status_code == 429:
            time.sleep(10); continue
        if r.status_code != 200:
            return None
        data = r.json()
        cards = data.get("data", [])
        all_cards.extend(cards)
        if len(all_cards) >= data.get("totalCount", 0) or not cards:
            break
        page += 1
        time.sleep(0.3)
    return all_cards

def parse_num(raw):
    if not raw: return None
    raw = str(raw).split("/")[0].strip()
    try: return int(raw)
    except:
        m = re.match(r'^[A-Za-z]+(\d+)$', raw)
        return int(m.group(1)) if m else None


class Command(BaseCommand):
    help = "Enrich DB from pokemontcg.io - verifies mapping first"

    def add_arguments(self, parser):
        parser.add_argument("set_code", type=str)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verify-only", action="store_true")

    def handle(self, *args, **options):
        set_code     = options["set_code"].upper()
        dry_run      = options["dry_run"]
        verify_only  = options["verify_only"]

        headers = {}
        if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
            headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY

        codes = list(CardSet.objects.values_list("code", flat=True)) if set_code == "ALL" else [set_code]

        grand_updated = 0
        failed = []
        no_map = []

        for code in codes:
            pid = SET_ID_MAP.get(code)
            if not pid:
                no_map.append(code)
                continue

            self.stdout.write(f"\n[{code}] -> ptcgio:{pid}")

            # Fetch ptcgio cards
            ptcgio_cards = fetch_cards(pid, headers)
            if not ptcgio_cards:
                self.stdout.write(f"  No cards returned — skipping")
                failed.append((code, pid, 0))
                continue

            # Verify: check card number overlap with DB
            db_nums = set(PokemonProduct.objects.filter(
                card_set__code=code, card_number__isnull=False
            ).values_list('card_number', flat=True).distinct())

            ptcgio_nums = {parse_num(c.get("number")) for c in ptcgio_cards}
            ptcgio_nums.discard(None)

            if not db_nums:
                self.stdout.write(f"  No DB records — skipping")
                continue

            overlap = db_nums & ptcgio_nums
            match_pct = len(overlap) / len(db_nums) * 100
            self.stdout.write(f"  Match: {match_pct:.0f}% ({len(overlap)}/{len(db_nums)} DB cards found in ptcgio)")

            if match_pct < 50:
                self.stdout.write(f"  MAPPING FAILED — skipping")
                failed.append((code, pid, match_pct))
                continue

            if verify_only:
                continue

            # Build lookup: card_number -> [cards]
            by_num = {}
            for c in ptcgio_cards:
                n = parse_num(c.get("number"))
                if n is not None:
                    by_num.setdefault(n, []).append(c)

            # Enrich
            db_records = list(PokemonProduct.objects.filter(
                card_set__code=code).prefetch_related('pokemon_types'))
            to_update = []
            updated = not_found = 0

            for p in db_records:
                matches = by_num.get(p.card_number, [])
                if not matches:
                    not_found += 1
                    continue

                # Pick best match by name
                card = matches[0]
                if len(matches) > 1:
                    pname = re.sub(r'\s*-\s*\d+/\d+$', '', p.name or '').strip().lower()
                    for m in matches:
                        if pname in m.get('name','').lower():
                            card = m; break

                if dry_run:
                    self.stdout.write(f"    [DRY] #{p.card_number} {p.name[:30]} -> {card.get('name','')[:30]}")
                    updated += 1
                    continue

                imgs = card.get("images", {})
                p.image_url        = imgs.get("large", "") or ""
                p.image_small_url  = imgs.get("small", "") or ""
                p.supertype        = card.get("supertype", "") or ""
                p.card_subtypes    = ", ".join(card.get("subtypes", [])) or ""
                hp = card.get("hp")
                p.hp               = int(hp) if hp and str(hp).isdigit() else None
                p.artist           = card.get("artist", "") or ""
                p.flavour_text     = card.get("flavorText", "") or ""
                pdx = card.get("nationalPokedexNumbers", [])
                p.pokedex_number   = pdx[0] if pdx else None
                wk = card.get("weaknesses", [])
                p.weakness_type    = wk[0].get("type","") if wk else ""
                p.weakness_value   = wk[0].get("value","") if wk else ""
                rs = card.get("resistances", [])
                p.resistance_type  = rs[0].get("type","") if rs else ""
                p.resistance_value = rs[0].get("value","") if rs else ""
                ret = card.get("retreatCost", [])
                p.retreat_cost     = len(ret) if ret else None
                ab = card.get("abilities", [])
                p.ability_name     = ab[0].get("name","") if ab else ""
                p.ability_type     = ab[0].get("type","") if ab else ""
                p.ability_text     = ab[0].get("text","") if ab else ""
                atks = card.get("attacks", [])
                a1 = atks[0] if atks else {}
                a2 = atks[1] if len(atks) > 1 else {}
                p.attack_1_name    = a1.get("name","") or ""
                p.attack_1_damage  = a1.get("damage","") or ""
                p.attack_1_text    = a1.get("text","") or ""
                p.attack_2_name    = a2.get("name","") or ""
                p.attack_2_damage  = a2.get("damage","") or ""
                p.attack_2_text    = a2.get("text","") or ""
                p.tcgplayer_id     = card.get("id","") or ""

                to_update.append(p)

                types = card.get("types", [])
                if types:
                    pts = [PokemonType.objects.get_or_create(name=t)[0] for t in types]
                    p.pokemon_types.set(pts)

                updated += 1

            if to_update:
                FIELDS = [
                    'image_url','image_small_url','supertype','card_subtypes',
                    'hp','artist','flavour_text','pokedex_number',
                    'weakness_type','weakness_value','resistance_type','resistance_value',
                    'retreat_cost','ability_name','ability_type','ability_text',
                    'attack_1_name','attack_1_damage','attack_1_text',
                    'attack_2_name','attack_2_damage','attack_2_text','tcgplayer_id',
                ]
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(to_update, FIELDS, batch_size=500)

            self.stdout.write(f"  Updated:{updated} | Not found:{not_found}")
            grand_updated += updated
            time.sleep(0.5)

        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"DONE — Total updated: {grand_updated}")
        if failed:
            self.stdout.write(f"FAILED MAPPINGS:")
            for c, p, r in failed:
                self.stdout.write(f"  {c} -> {p} ({r:.0f}% match)")
        if no_map:
            self.stdout.write(f"NO MAPPING: {', '.join(no_map)}")