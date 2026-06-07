# -*- coding: utf-8 -*-
"""
enrich_bulbapedia.py - PokeBulk SA
Enriches card data from Bulbapedia MediaWiki API.
Covers MEG era, TG sets, BLK, WHT and other sets not on pokemontcg.io.

Fetches: HP, type, weakness, resistance, retreat, artist,
         evolves from, stage, ability, attacks, pokedex number

NEVER touches: price, stock, variant, image_url, card_number, name

Usage:
  python manage.py enrich_bulbapedia CRI --verify-only
  python manage.py enrich_bulbapedia MEG PFL ASC POR CRI BLK WHT
  python manage.py enrich_bulbapedia ALL
  python manage.py enrich_bulbapedia CRI --dry-run
  python manage.py enrich_bulbapedia CRI --overwrite

Run with DATABASE_URL uncommented in .env
"""
import requests, time, re
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import PokemonProduct, CardSet

BULBA_API   = "https://bulbapedia.bulbagarden.net/w/api.php"
TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS     = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

BULBA_SETS = {
    "MEG":    ("Mega Evolution",          "regular", 24380),
    "PFL":    ("Phantasmal Flames",       "regular", 24448),
    "MEP":    ("Mega Evolution Promos",   "regular", 24451),
    "MEE":    ("Mega Evolution Energies", "regular", 24461),
    "ASC":    ("Ascended Heroes",         "regular", 24541),
    "POR":    ("Perfect Order",           "regular", 24587),
    "CRI":    ("Chaos Rising",            "regular", 24655),
    "BLK":    ("Black Bolt",              "regular", 24325),
    "WHT":    ("White Flare",             "regular", 24326),
    "BRSTG":  ("Brilliant Stars",         "tg",      3020),
    "ASRTG":  ("Astral Radiance",         "tg",      3068),
    "LORTG":  ("Lost Origin",             "tg",      3172),
    "SITTG":  ("Silver Tempest",          "tg",      17674),
    "CRZGG":  ("Crown Zenith",            "tg",      17689),
    "SHFSV":  ("Shining Fates",           "sv",      2781),
    "HIFSV":  ("Hidden Fates",            "sv",      2594),
}

ENRICH_FIELDS = [
    "hp", "card_subtypes", "supertype",
    "weakness_type", "weakness_value",
    "resistance_type", "resistance_value",
    "retreat_cost", "artist",
    "ability_name", "ability_type", "ability_text",
    "attack_1_name", "attack_1_damage", "attack_1_text",
    "attack_2_name", "attack_2_damage", "attack_2_text",
    "pokedex_number",
]


def fetch_tcgcsv_numbers(group_id):
    try:
        r = requests.get(
            f"{TCGCSV_BASE}/{group_id}/products",
            headers=HEADERS, timeout=30
        )
        if r.status_code != 200:
            return {}
        products = r.json().get("results", [])
        mapping = {}
        for p in products:
            pid = p["productId"]
            num = next(
                (e["value"] for e in p.get("extendedData", [])
                 if e["name"] == "Number"),
                ""
            )
            if num:
                num = num.split("/")[0].strip()
            mapping[pid] = num
        return mapping
    except Exception:
        return {}


def fetch_bulba_wikitext(page_title):
    try:
        r = requests.get(BULBA_API, params={
            "action": "parse",
            "page":   page_title,
            "prop":   "wikitext",
            "format": "json"
        }, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        data = r.json()
        if "error" in data:
            return None, data["error"].get("info", "Unknown error")
        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        return wikitext, None
    except Exception as e:
        return None, str(e)


def extract_template_block(wikitext, template_name):
    """Extract content of a template block handling nested {{ }}"""
    blocks = []
    parts = wikitext.split(f'{{{{{template_name}')
    for part in parts[1:]:
        depth = 1
        i = 0
        while i < len(part) and depth > 0:
            if part[i:i+2] == '{{':
                depth += 1
                i += 2
            elif part[i:i+2] == '}}':
                depth -= 1
                if depth == 0:
                    blocks.append(part[:i])
                    break
                i += 2
            else:
                i += 1
    return blocks


def get_field_from_block(block, field):
    m = re.search(rf'\|{field}=([^\n|}}]+)', block)
    return m.group(1).strip() if m else ""


def parse_wikitext(wikitext):
    def get(field):
        m = re.search(rf'\|{field}=([^\n|}}]+)', wikitext)
        return m.group(1).strip() if m else ""

    # Artist from caption "Illus. [[Name]]"
    caption = get("caption")
    artist_match = re.search(r'Illus\.\s*\[\[([^\]|]+)', caption)
    artist = artist_match.group(1).strip() if artist_match else get("illus")

    # Pokedex from evoicon
    dex = get("evoicon")
    pokedex = int(dex) if dex and dex.isdigit() else None

    # Also check ndex in Carddex template
    if not pokedex:
        dex2 = get("ndex")
        if dex2 and dex2.isdigit():
            pokedex = int(dex2)

    # HP
    hp_raw = get("hp")
    hp = int(hp_raw) if hp_raw and hp_raw.isdigit() else None

    # Retreat cost
    retreat_raw = get("retreatcost")
    retreat = int(retreat_raw) if retreat_raw and retreat_raw.isdigit() else None

    # Parse attacks using depth-aware template extraction
    attack_blocks = extract_template_block(wikitext, "Cardtext/Attack")
    attacks = []
    for block in attack_blocks:
        name   = get_field_from_block(block, "name")
        damage = get_field_from_block(block, "damage")
        effect = get_field_from_block(block, "effect")
        if name:
            attacks.append({
                "name":   name,
                "damage": damage,
                "text":   effect,
            })

    # Parse ability using depth-aware template extraction
    ability_name = ability_text = ability_type = ""
    ability_blocks = extract_template_block(wikitext, "Cardtext/Ability")
    if ability_blocks:
        ab = ability_blocks[0]
        ability_name = get_field_from_block(ab, "name")
        ability_text = get_field_from_block(ab, "effect")
        ability_type = get_field_from_block(ab, "type") or "Ability"

    return {
        "hp":             hp,
        "type":           get("type"),
        "weakness":       get("weakness"),
        "resistance":     get("resistance"),
        "retreat_cost":   retreat,
        "evostage":       get("evostage"),
        "evolves_from":   get("evospecies"),
        "artist":         artist,
        "ability_name":   ability_name,
        "ability_type":   ability_type,
        "ability_text":   ability_text,
        "attack_1_name":  attacks[0]["name"]   if len(attacks) > 0 else "",
        "attack_1_damage":attacks[0]["damage"] if len(attacks) > 0 else "",
        "attack_1_text":  attacks[0]["text"]   if len(attacks) > 0 else "",
        "attack_2_name":  attacks[1]["name"]   if len(attacks) > 1 else "",
        "attack_2_damage":attacks[1]["damage"] if len(attacks) > 1 else "",
        "attack_2_text":  attacks[1]["text"]   if len(attacks) > 1 else "",
        "pokedex_number": pokedex,
    }


def clean_name(name):
    name = re.sub(r'\s*-\s*\d+/\d+\s*$', '', name).strip()
    name = re.sub(r'\s*\([^)]+\)\s*$', '', name).strip()
    return name.replace(' ', '_')


def build_page_title(card_name, set_name, card_number):
    name = clean_name(card_name)
    set_clean = set_name.replace(' ', '_')
    return f"{name}_({set_clean}_{card_number})"


def get_alternate_titles(card_name, set_name, num_for_title):
    alts = []

    # lowercase ex: "Beedrill EX" -> "Beedrill ex"
    name_lower_ex = re.sub(r'\bEX\b', 'ex', card_name)
    if name_lower_ex != card_name:
        alts.append(build_page_title(name_lower_ex, set_name, num_for_title))

    # GX with dash: "Charizard GX" -> "Charizard-GX"
    name_dash_gx = re.sub(r'\bGX\b', '-GX', card_name)
    if name_dash_gx != card_name:
        alts.append(build_page_title(name_dash_gx, set_name, num_for_title))

    # Remove suffix entirely
    name_no_suffix = re.sub(
        r'\s*(ex|EX|V|VMAX|VSTAR|GX|V-UNION|-GX|-EX)\s*$', '', card_name
    ).strip()
    if name_no_suffix != card_name:
        alts.append(build_page_title(name_no_suffix, set_name, num_for_title))

    return alts


def apply_to_product(p, parsed, overwrite=False):
    changed = False

    def set_field(field, value):
        nonlocal changed
        if value is None or value == "":
            return
        current = getattr(p, field, None)
        if overwrite or not current:
            if current != value:
                setattr(p, field, value)
                changed = True

    set_field("hp",             parsed["hp"])
    set_field("card_subtypes",  parsed["type"])
    set_field("weakness_type",  parsed["weakness"])
    if parsed["weakness"]:
        set_field("weakness_value", "x2")
    set_field("resistance_type",  parsed["resistance"])
    if parsed["resistance"]:
        set_field("resistance_value", "-30")
    set_field("retreat_cost",   parsed["retreat_cost"])
    set_field("artist",         parsed["artist"])
    set_field("ability_name",   parsed["ability_name"])
    set_field("ability_type",   parsed["ability_type"])
    set_field("ability_text",   parsed["ability_text"])
    set_field("attack_1_name",  parsed["attack_1_name"])
    set_field("attack_1_damage",parsed["attack_1_damage"])
    set_field("attack_1_text",  parsed["attack_1_text"])
    set_field("attack_2_name",  parsed["attack_2_name"])
    set_field("attack_2_damage",parsed["attack_2_damage"])
    set_field("attack_2_text",  parsed["attack_2_text"])
    set_field("pokedex_number", parsed["pokedex_number"])

    return changed


class Command(BaseCommand):
    help = "Enrich card data from Bulbapedia for sets not on pokemontcg.io"

    def add_arguments(self, parser):
        parser.add_argument("set_codes", nargs="+", type=str)
        parser.add_argument("--dry-run",     action="store_true")
        parser.add_argument("--verify-only", action="store_true")
        parser.add_argument("--overwrite",   action="store_true")
        parser.add_argument("--delay",       type=float, default=0.5)

    def handle(self, *args, **options):
        codes     = options["set_codes"]
        dry_run   = options["dry_run"]
        verify    = options["verify_only"]
        overwrite = options["overwrite"]
        delay     = options["delay"]

        if len(codes) == 1 and codes[0].upper() == "ALL":
            codes = list(BULBA_SETS.keys())

        codes = [c.upper() for c in codes]

        self.stdout.write("Bulbapedia Card Enrichment")
        self.stdout.write(f"Sets: {', '.join(codes)}")
        self.stdout.write(f"Dry run:{dry_run} | Verify:{verify} | Overwrite:{overwrite}")
        self.stdout.write("=" * 60)

        grand_updated = grand_not_found = grand_skipped = 0

        for code in codes:
            if code not in BULBA_SETS:
                self.stdout.write(f"\n[{code}] Not in BULBA_SETS - skipping")
                continue

            set_name, fmt, tcgcsv_gid = BULBA_SETS[code]

            try:
                db_set = CardSet.objects.get(code=code)
            except CardSet.DoesNotExist:
                self.stdout.write(f"\n[{code}] Not in DB - skipping")
                continue

            self.stdout.write(f"\n[{code}] {set_name} (format={fmt})")

            tcgcsv_numbers = {}
            if fmt in ("tg", "sv") and tcgcsv_gid:
                self.stdout.write(f"  Fetching card numbers from TCGCSV...")
                tcgcsv_numbers = fetch_tcgcsv_numbers(tcgcsv_gid)
                self.stdout.write(f"  Got {len(tcgcsv_numbers)} numbers")

            if fmt == "regular":
                identifiers = list(
                    PokemonProduct.objects.filter(
                        card_set=db_set,
                        card_number__isnull=False
                    ).values_list("card_number", flat=True)
                    .distinct().order_by("card_number")
                )
            else:
                identifiers = list(
                    PokemonProduct.objects.filter(
                        card_set=db_set,
                        tcgcsv_product_id__isnull=False
                    ).values_list("tcgcsv_product_id", flat=True)
                    .distinct()
                )

            if verify:
                identifiers = identifiers[:3]

            self.stdout.write(f"  Cards to enrich: {len(identifiers)}")

            to_update = []
            updated = not_found = skipped = 0

            for identifier in identifiers:
                if fmt == "regular":
                    card_number = identifier
                    sample = PokemonProduct.objects.filter(
                        card_set=db_set,
                        card_number=card_number
                    ).first()
                    if not sample:
                        not_found += 1
                        continue
                    num_for_title = card_number
                else:
                    pid = identifier
                    num_str = tcgcsv_numbers.get(pid, "")
                    if not num_str:
                        not_found += 1
                        continue
                    sample = PokemonProduct.objects.filter(
                        card_set=db_set,
                        tcgcsv_product_id=pid
                    ).first()
                    if not sample:
                        not_found += 1
                        continue
                    num_for_title = num_str

                # Build primary page title and try it
                page_title = build_page_title(sample.name, set_name, num_for_title)
                wikitext, error = fetch_bulba_wikitext(page_title)

                # Try alternate titles if not found
                if error or not wikitext:
                    for alt_title in get_alternate_titles(
                        sample.name, set_name, num_for_title
                    ):
                        if alt_title == page_title:
                            continue
                        wikitext, error = fetch_bulba_wikitext(alt_title)
                        if wikitext and not error:
                            page_title = alt_title
                            break
                        time.sleep(0.2)

                if error or not wikitext:
                    not_found += 1
                    if verify:
                        self.stdout.write(
                            f"  NOT FOUND: {page_title} | {error}"
                        )
                    time.sleep(delay)
                    continue

                parsed = parse_wikitext(wikitext)

                if verify:
                    self.stdout.write(f"  FOUND: {page_title}")
                    self.stdout.write(
                        f"    HP:{parsed['hp']} Type:{parsed['type']} "
                        f"Weakness:{parsed['weakness']} Retreat:{parsed['retreat_cost']}"
                    )
                    self.stdout.write(
                        f"    Artist:{parsed['artist']} Evolves:{parsed['evolves_from']}"
                    )
                    self.stdout.write(
                        f"    Ability:{parsed['ability_name']} "
                        f"Atk1:{parsed['attack_1_name']} "
                        f"Atk2:{parsed['attack_2_name']}"
                    )
                    time.sleep(delay)
                    updated += 1
                    continue

                if dry_run:
                    updated += 1
                    time.sleep(delay)
                    continue

                if fmt == "regular":
                    all_variants = PokemonProduct.objects.filter(
                        card_set=db_set,
                        card_number=identifier
                    )
                else:
                    all_variants = PokemonProduct.objects.filter(
                        card_set=db_set,
                        tcgcsv_product_id=pid
                    )

                changed_any = False
                for p in all_variants:
                    if apply_to_product(p, parsed, overwrite):
                        to_update.append(p)
                        changed_any = True

                if changed_any:
                    updated += 1
                else:
                    skipped += 1

                time.sleep(delay)

                if len(to_update) >= 50:
                    with transaction.atomic():
                        PokemonProduct.objects.bulk_update(
                            to_update, ENRICH_FIELDS, batch_size=200
                        )
                    self.stdout.write(f"  Saved {len(to_update)} records...")
                    to_update = []

            if to_update and not dry_run:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(
                        to_update, ENRICH_FIELDS, batch_size=200
                    )

            self.stdout.write(
                f"  Updated:{updated} | "
                f"Not found:{not_found} | "
                f"Already complete:{skipped}"
            )
            grand_updated   += updated
            grand_not_found += not_found
            grand_skipped   += skipped

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"DONE")
        self.stdout.write(f"  Total updated:    {grand_updated}")
        self.stdout.write(f"  Not found:        {grand_not_found}")
        self.stdout.write(f"  Already complete: {grand_skipped}")
        if dry_run:
            self.stdout.write(f"  (DRY RUN - nothing saved)")
