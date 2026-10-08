"""
enrich_only.py - PokeBulk SA
Sources:
  1. pokemontcg.io — primary: images, attacks, abilities, HP, artist, types
  2. TCGCSV — fallback: imageUrl where pokemontcg.io has no data (MEG era)

NEVER touches price, stock, variant, card_number, rarity.

Usage:
  python manage.py enrich_only ALL --verify-only
  python manage.py enrich_only ALL
  python manage.py enrich_only ASC
  python manage.py enrich_only ALL --dry-run
  python manage.py enrich_only ALL --tcgcsv-only  (TCGCSV images only, skip ptcgio)
"""
import requests, time, re
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from products.models import PokemonProduct, CardSet, PokemonType

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
TCGCSV_HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

# TCGCSV group IDs for MEG era sets
TCGCSV_MEG_GROUPS = {
    "MEG": 24380,
    "PFL": 24448,
    "ASC": 24541,
    "POR": 24587,
    "CRI": 24655,
}

SET_ID_MAP = {
    # WotC Era - VERIFIED
    'BS':     'base1',
    'BS2':    'base4',
    'BSS':    'basep',
    'FO':     'base3',
    'JU':     'base2',
    'TR':     'base5',
    'G1':     'gym1',
    'G2':     'gym2',
    'SI1':    'si1',
    # WotC Neo Era - VERIFIED
    'N1':     'neo1',
    'N2':     'neo2',
    'N3':     'neo3',
    'N4':     'neo4',
    # WotC Legendary Era - VERIFIED
    'LC':     'base6',
    # WotC Other (e-Card) Era - VERIFIED
    'EX':     'ecard1',
    'AQ':     'ecard2',
    'SK':     'ecard3',
    # EX Era - VERIFIED
    'RS':     'ex1',
    'SS':     'ex2',
    'DR':     'ex3',
    'MA':     'ex4',
    'HL':     'ex5',
    'RG':     'ex6',
    'TRR':    'ex7',
    'DX':     'ex8',
    'EM':     'ex9',
    'UF':     'ex10',
    'DS':     'ex11',
    'LM':     'ex12',
    'HP':     'ex13',
    'CG':     'ex14',
    'DF':     'ex15',
    'PK':     'ex16',
    # DP Era - VERIFIED
    'DP':     'dp1',
    'MT':     'dp2',
    'SW':     'dp3',
    'GE':     'dp4',
    'MD':     'dp5',
    'LA':     'dp6',
    'SF':     'dp7',
    'PL':     'pl1',
    'RR':     'pl2',
    'SV':     'pl3',
    'AR':     'pl4',
    # HGSS Era - VERIFIED
    'HS':     'hgss1',
    'UL':     'hgss2',
    'UD':     'hgss3',
    'TM':     'hgss4',
    'CoL':    'col1',
    # BW Era - VERIFIED
    'BLW':    'bw1',
    'EPO':    'bw2',
    'NVI':    'bw3',
    'NXD':    'bw4',
    'DEX':    'bw5',
    'DRX':    'bw6',
    'DRV':    'dv1',
    'BCR':    'bw7',
    'PLS':    'bw8',
    'PLF':    'bw9',
    'PLB':    'bw10',
    'LTR':    'bw11',
    # XY Era - VERIFIED
    'KSS':    'xy0',
    'XY':     'xy1',
    'FLF':    'xy2',
    'FFI':    'xy3',
    'PHF':    'xy4',
    'PRC':    'xy5',
    'DCR':    'dc1',
    'ROS':    'xy6',
    'AOR':    'xy7',
    'BKT':    'xy8',
    'BKP':    'xy9',
    'GEN':    'g1',
    'FCO':    'xy10',
    'STS':    'xy11',
    'EVO':    'xy12',
    # SM Era - VERIFIED - DB uses SM01-SM12 NOT SUM/GRI/BUS
    'SM01':   'sm1',
    'SM02':   'sm2',
    'SM03':   'sm3',
    'SHL':    'sm35',
    'SM04':   'sm4',
    'SM05':   'sm5',
    'SM06':   'sm6',
    'CES':    'sm7',
    'DRM':    'sm75',
    'SM8':    'sm8',
    'SM9':    'sm9',
    'SM10':   'sm10',
    'SM11':   'sm11',
    'HIF':    'sm115',
    'HIFSV':  'sma',
    'SM12':   'sm12',
    # SWSH Era - VERIFIED - DB uses SWSH01/02/03 etc
    'SWSH01': 'swsh1',
    'SWSH02': 'swsh2',
    'SWSH03': 'swsh3',
    'CHP':    'swsh35',
    'SWSH04': 'swsh4',
    'SHF':    'swsh45',
    'SHFSV':  'swsh45sv',
    'SWSH05': 'swsh5',
    'SWSH06': 'swsh6',
    'SWSH07': 'swsh7',
    'CLB':    'cel25',
    'CCC':    'cel25c',
    'SWSH08': 'swsh8',
    'SWSH09': 'swsh9',
    'BRSTG':  'swsh9tg',
    'SWSH10': 'swsh10',
    'ASRTG':  'swsh10tg',
    'PGO':    'pgo',
    'SWSH11': 'swsh11',
    'LORTG':  'swsh11tg',
    'SWSH12': 'swsh12',
    'SITTG':  'swsh12tg',
    'CRZ':    'swsh12pt5',
    'CRZGG':  'swsh12pt5gg',
    # SWSH Era - 2026-10-08: the DB's actual codes for the main sets are the
    # 3-letter ones below (found via enrich_mega --era-from --report), not
    # SWSH01..12 above. Both are kept so either naming enriches. Number overlap
    # is verified at run time (<50% match is skipped), so a wrong guess is safe.
    'SSH':    'swsh1',
    'RCL':    'swsh2',
    'DAA':    'swsh3',
    'VIV':    'swsh4',
    'BST':    'swsh5',
    'CRE':    'swsh6',
    'EVS':    'swsh7',
    'FST':    'swsh8',
    'BRS':    'swsh9',
    'ASR':    'swsh10',
    'LOR':    'swsh11',
    'SIT':    'swsh12',
    # Promos / specials
    'PR-SWSH': 'swshp',
    'SMP':    'smp',
    'SVP':    'svp',
    'SVE':    'sve',
    'DET':    'det1',
    # SV Era - VERIFIED - DB uses SVI/PAL/OBF/PAR/PAF NOT SV1/SV2/SV3
    'SVI':    'sv1',
    'PAL':    'sv2',
    'OBF':    'sv3',
    'MEW':    'sv3pt5',
    'PAR':    'sv4',
    'PAF':    'sv4pt5',
    'TEF':    'sv5',
    'TWM':    'sv6',
    'SFA':    'sv6pt5',
    'SCR':    'sv7',
    'SSP':    'sv8',
    'PRE':    'sv8pt5',
    'JTG':    'sv9',
    'DRI':    'sv10',
    # MEG Era - NOT YET on pokemontcg.io, handled by TCGCSV image fallback
    # 'MEG':  'me1',
    # 'PFL':  'me2',
    # 'ASC':  'me2pt5',
    # 'POR':  'me3',
    # 'CRI':  'me4',
}


def fetch_ptcgio_cards(ptcgio_id, headers):
    # 2026-10-08: pokemontcg.io is slow/flaky (frequent timeouts and 504s).
    # Smaller pages (100 instead of 250), 5 attempts per page with growing
    # backoff, and 5xx treated as retryable instead of a hard fail.
    all_cards, page = [], 1
    while True:
        r = None
        for attempt in range(5):
            try:
                r = requests.get(
                    f"https://api.pokemontcg.io/v2/cards"
                    f"?q=set.id:{ptcgio_id}&pageSize=100&page={page}&orderBy=number",
                    headers=headers, timeout=90)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                r = None
            if r is not None and r.status_code == 200:
                break
            if r is not None and r.status_code not in (429, 500, 502, 503, 504):
                return None
            time.sleep(8 * (attempt + 1))
        if r is None or r.status_code != 200:
            return None
        data = r.json()
        cards = data.get("data", [])
        all_cards.extend(cards)
        if len(all_cards) >= data.get("totalCount", 0) or not cards:
            break
        page += 1
        time.sleep(0.3)
    return all_cards


def fetch_tcgcsv_images(group_id):
    """Fetch product imageUrl map from TCGCSV: {product_id: image_url}"""
    try:
        r = requests.get(
            f"{TCGCSV_BASE}/{group_id}/products",
            headers=TCGCSV_HEADERS, timeout=30)
        if r.status_code != 200:
            return {}
        products = r.json().get("results", [])
        return {
            p["productId"]: p.get("imageUrl", "") or ""
            for p in products
            if p.get("imageUrl")
        }
    except Exception:
        return {}


def parse_num(raw):
    if not raw:
        return None
    raw = str(raw).split("/")[0].strip()
    try:
        return int(raw)
    except ValueError:
        m = re.match(r'^[A-Za-z]+(\d+)$', raw)
        return int(m.group(1)) if m else None


class Command(BaseCommand):
    help = "Enrich DB from pokemontcg.io (primary) + TCGCSV images (fallback)"

    def add_arguments(self, parser):
        parser.add_argument("set_code", type=str)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verify-only", action="store_true",
                            help="Check mappings only, no changes")
        parser.add_argument("--tcgcsv-only", action="store_true",
                            help="Only fetch TCGCSV images, skip pokemontcg.io")

    def handle(self, *args, **options):
        set_code    = options["set_code"].upper()
        dry_run     = options["dry_run"]
        verify_only = options["verify_only"]
        tcgcsv_only = options["tcgcsv_only"]

        ptcgio_headers = {}
        if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
            ptcgio_headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY

        codes = (list(CardSet.objects.values_list("code", flat=True))
                 if set_code == "ALL" else [set_code])

        grand_updated  = 0
        grand_tcgcsv   = 0
        failed         = []
        no_map         = []
        skipped_empty  = []

        for code in codes:

            # ── TCGCSV-only path (MEG era or explicit flag) ──────────────
            if tcgcsv_only or code in TCGCSV_MEG_GROUPS:
                gid = TCGCSV_MEG_GROUPS.get(code)
                if not gid:
                    if tcgcsv_only:
                        no_map.append(code)
                    continue

                self.stdout.write(f"\n[{code}] TCGCSV image fallback (groupId={gid})")

                db_records = list(PokemonProduct.objects.filter(
                    card_set__code=code,
                    tcgcsv_product_id__isnull=False
                ))
                if not db_records:
                    self.stdout.write(f"  No DB records — skipping")
                    skipped_empty.append(code)
                    continue

                if verify_only:
                    self.stdout.write(f"  {len(db_records)} records, TCGCSV gid={gid}")
                    continue

                img_map = fetch_tcgcsv_images(gid)
                self.stdout.write(f"  TCGCSV images available: {len(img_map)}")

                to_update = []
                updated = 0
                for p in db_records:
                    img = img_map.get(p.tcgcsv_product_id, "")
                    if img and not p.image_url:
                        if dry_run:
                            self.stdout.write(
                                f"  [DRY] #{p.card_number} {(p.name or '')[:30]} -> {img[:60]}")
                        else:
                            p.image_url = img
                            p.image_small_url = img
                            to_update.append(p)
                        updated += 1

                if to_update and not dry_run:
                    with transaction.atomic():
                        PokemonProduct.objects.bulk_update(
                            to_update, ['image_url', 'image_small_url'], batch_size=500)

                self.stdout.write(f"  Images updated: {updated}")
                grand_tcgcsv += updated
                continue

            # ── pokemontcg.io path ───────────────────────────────────────
            pid = SET_ID_MAP.get(code)
            if not pid:
                no_map.append(code)
                continue

            self.stdout.write(f"\n[{code}] -> ptcgio:{pid}")

            ptcgio_cards = fetch_ptcgio_cards(pid, ptcgio_headers)
            if not ptcgio_cards:
                self.stdout.write(f"  No cards returned or timeout — skipping")
                failed.append((code, pid, 0))
                continue

            # Verify card number overlap
            db_nums = set(
                PokemonProduct.objects.filter(
                    card_set__code=code, card_number__isnull=False
                ).values_list('card_number', flat=True).distinct()
            )

            if not db_nums:
                self.stdout.write(f"  No DB records — skipping")
                skipped_empty.append(code)
                continue

            ptcgio_nums = {parse_num(c.get("number")) for c in ptcgio_cards}
            ptcgio_nums.discard(None)
            overlap    = db_nums & ptcgio_nums
            match_pct  = len(overlap) / len(db_nums) * 100

            self.stdout.write(
                f"  Match: {match_pct:.0f}% "
                f"({len(overlap)}/{len(db_nums)} DB | ptcgio:{len(ptcgio_nums)})"
            )

            if match_pct < 50:
                self.stdout.write(f"  MAPPING FAILED — skipping")
                failed.append((code, pid, match_pct))
                continue

            if verify_only:
                self.stdout.write(f"  Mapping OK")
                continue

            # Build lookup: card_number -> [cards]
            by_num = {}
            for c in ptcgio_cards:
                n = parse_num(c.get("number"))
                if n is not None:
                    by_num.setdefault(n, []).append(c)

            db_records = list(
                PokemonProduct.objects.filter(card_set__code=code)
                .prefetch_related('pokemon_types')
            )
            to_update  = []
            updated = not_found = tcgcsv_fallback = 0

            # Fetch TCGCSV images as fallback for this set if available
            tcgcsv_gid = TCGCSV_MEG_GROUPS.get(code)
            tcgcsv_imgs = fetch_tcgcsv_images(tcgcsv_gid) if tcgcsv_gid else {}

            for p in db_records:
                matches = by_num.get(p.card_number, [])

                if not matches:
                    # Try TCGCSV image fallback
                    if tcgcsv_imgs and p.tcgcsv_product_id and not p.image_url:
                        img = tcgcsv_imgs.get(p.tcgcsv_product_id, "")
                        if img:
                            if not dry_run:
                                p.image_url = img
                                p.image_small_url = img
                                to_update.append(p)
                            tcgcsv_fallback += 1
                    else:
                        not_found += 1
                    continue

                # Best name match when multiple cards at same number
                card = matches[0]
                if len(matches) > 1:
                    pname = re.sub(r'\s*-\s*\d+/\d+$', '', p.name or '').strip().lower()
                    for m in matches:
                        if pname in m.get('name', '').lower():
                            card = m
                            break

                if dry_run:
                    self.stdout.write(
                        f"  [DRY] #{p.card_number} {(p.name or '')[:30]}"
                        f" -> {card.get('name','')[:30]}")
                    updated += 1
                    continue

                # Apply all enrichment fields
                # 2026-10-08: images are NO LONGER written from here. This used
                # to overwrite image_url with pokemontcg.io links (or blank it)
                # on every run, which would replace the R2-hosted images
                # (images.pokebulk.co.za) with external hotlinks -- against the
                # "R2 always for images" rule. Card images are handled by the
                # R2 upload commands only; this command is data-only now.

                # 2026-10-07: only write a value when the API actually has
                # one -- a thin API record used to wipe good existing data
                # (HP, attacks, artist...) with blanks.
                def put(field, value):
                    if value not in (None, ""):
                        setattr(p, field, value)

                subs = card.get("subtypes", []) or []
                put("supertype",     card.get("supertype", ""))
                put("card_subtypes", ", ".join(subs))
                hp = card.get("hp")
                put("hp",            int(hp) if hp and str(hp).isdigit() else None)
                put("artist",        card.get("artist", ""))
                put("flavour_text",  card.get("flavorText", ""))
                pdx = card.get("nationalPokedexNumbers", [])
                put("pokedex_number", pdx[0] if pdx else None)
                wk = card.get("weaknesses", [])
                put("weakness_type",  wk[0].get("type", "") if wk else "")
                put("weakness_value", wk[0].get("value", "") if wk else "")
                rs = card.get("resistances", [])
                put("resistance_type",  rs[0].get("type", "") if rs else "")
                put("resistance_value", rs[0].get("value", "") if rs else "")
                ret = card.get("retreatCost", [])
                put("retreat_cost",  len(ret) if ret else None)
                ab = card.get("abilities", []) or []
                for i, prefix in enumerate(("ability", "ability_2")):
                    a = ab[i] if len(ab) > i else {}
                    put(f"{prefix}_name", a.get("name", ""))
                    put(f"{prefix}_type", a.get("type", ""))
                    put(f"{prefix}_text", a.get("text", ""))
                atks = card.get("attacks", []) or []
                for i in range(3):
                    a = atks[i] if len(atks) > i else {}
                    put(f"attack_{i+1}_name",   a.get("name", ""))
                    put(f"attack_{i+1}_damage", a.get("damage", ""))
                    put(f"attack_{i+1}_text",   a.get("text", ""))
                    put(f"attack_{i+1}_cost",   ",".join(a.get("cost", []) or []))
                put("tcgplayer_id", card.get("id", ""))
                # 2026-10-07 gap-fill
                stage = next((s for s in subs if s in ("Basic", "Stage 1", "Stage 2", "MEGA", "Mega", "VMAX", "VSTAR", "V-UNION", "BREAK", "Restored")), "")
                put("stage",         stage)
                put("evolves_from",  card.get("evolvesFrom", ""))
                put("evolves_to",    ", ".join(card.get("evolvesTo", []) or []))
                put("rules_text",    " ".join(card.get("rules", []) or []))
                at = card.get("ancientTrait") or {}
                put("ancient_trait", f"{at.get('name', '')}: {at.get('text', '')}".strip(": ") if at else "")
                put("card_level",    card.get("level", ""))
                # Fill-only (never overwrite): per-card regulation mark and
                # the API's own legalities where we have none yet.
                if not p.regulation_mark:
                    put("regulation_mark", card.get("regulationMark", ""))
                lg = card.get("legalities", {}) or {}
                if p.legal_standard is None and lg.get("standard"):
                    p.legal_standard = (lg["standard"] == "Legal")
                if p.legal_expanded is None and lg.get("expanded"):
                    p.legal_expanded = (lg["expanded"] == "Legal")

                to_update.append(p)

                types = card.get("types", [])
                if types:
                    pts = [PokemonType.objects.get_or_create(name=t)[0] for t in types]
                    p.pokemon_types.set(pts)

                updated += 1

            FIELDS = [
                'image_url', 'image_small_url', 'supertype', 'card_subtypes',
                'hp', 'artist', 'flavour_text', 'pokedex_number',
                'weakness_type', 'weakness_value', 'resistance_type', 'resistance_value',
                'retreat_cost', 'ability_name', 'ability_type', 'ability_text',
                'attack_1_name', 'attack_1_damage', 'attack_1_text',
                'attack_2_name', 'attack_2_damage', 'attack_2_text',
                'tcgplayer_id',
                'attack_1_cost', 'attack_2_cost',
                'attack_3_name', 'attack_3_damage', 'attack_3_text', 'attack_3_cost',
                'ability_2_name', 'ability_2_type', 'ability_2_text',
                'stage', 'evolves_from', 'evolves_to', 'rules_text',
                'ancient_trait', 'card_level',
                'regulation_mark', 'legal_standard', 'legal_expanded',
            ]
            if to_update and not dry_run:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(to_update, FIELDS, batch_size=500)

            self.stdout.write(
                f"  Updated:{updated} | Not found:{not_found}"
                f" | TCGCSV fallback:{tcgcsv_fallback}")
            grand_updated += updated
            time.sleep(0.5)

        # ── Summary ──────────────────────────────────────────────────────
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"DONE")
        self.stdout.write(f"  ptcgio enriched:    {grand_updated}")
        self.stdout.write(f"  TCGCSV images:      {grand_tcgcsv}")

        if failed:
            self.stdout.write(f"\nFAILED MAPPINGS:")
            for c, p, r in failed:
                self.stdout.write(f"  {c} -> {p} ({r:.0f}% match)")

        if no_map:
            self.stdout.write(f"\nNO MAPPING (not in SET_ID_MAP):")
            self.stdout.write(f"  {', '.join(no_map)}")

        if skipped_empty:
            self.stdout.write(f"\nSKIPPED (no DB records):")
            self.stdout.write(f"  {', '.join(skipped_empty)}")