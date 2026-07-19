"""
PokeBulk SA -- Serebii Enrichment Script
==========================================
Confirmed 2026-07-13 (see memory edit re: Serebii): Serebii has full,
genuine card data live for Pitch Black well ahead of Bulbapedia's own
partial rollout for that same set, and is generally a strong source for
recent Mega Evolution era sets.

IMPORTANT DIFFERENCE FROM enrich_bulbapedia.py: Bulbapedia has a proper
MediaWiki API returning clean structured wikitext (|illus=, |ndex=,
|regulation= etc). Serebii has NO API -- this scrapes raw HTML from
static card pages instead. That's a fundamentally less reliable parsing
target than wikitext, and I was not able to verify the exact HTML
structure against real source (only rendered/converted page content),
so the regex patterns below are a best-effort first draft, not a
proven-correct port like the Bulbapedia script.

DO NOT run a full batch first. Run --test-one against a few real cards
first and manually check the printed fields are actually correct.

Usage:
    python enrich_serebii.py --test-one PBL 48        # single card, prints everything, saves nothing
    python enrich_serebii.py ALL --verify-only          # match-rate check per set, no DB writes
    python enrich_serebii.py PBL --dry-run              # shows what would be written
    python enrich_serebii.py PBL                        # actually writes

Only fills fields that are currently BLANK on each row -- never
overwrites existing Bulbapedia/TCGCSV data. Never touches price, stock,
variant, or card_number, same rule as enrich_only.py.
"""

import sys
import os
import re
import time
import argparse
import html as html_module
import requests

UA = "PokeBulkSA/1.0.0 (enquiries@pokebulk.co.za)"
DELAY = 0.3
TIMEOUT = 20

# Confirmed working (2026-07-13): pitchblack, whiteflare.
# Everything else below is my best guess at Serebii's slug convention
# (lowercase, no spaces/ampersands/punctuation) based on the confirmed
# pattern -- NOT individually verified. Run --verify-only before trusting
# any set not marked CONFIRMED.
SEREBII_SET_SLUGS = {
    'PBL': 'pitchblack',      # CONFIRMED 2026-07-13
    'WHT': 'whiteflare',      # CONFIRMED 2026-07-13
    'BLK': 'blackbolt',       # unverified, matches known convention
    'CRI': 'chaosrising',     # unverified
    'POR': 'perfectorder',    # unverified
    'ASC': 'ascendedheroes',  # unverified
    'PFL': 'phantasmalflames',  # unverified
    'MEG': 'megaevolution',   # unverified
    'MEW': '151',             # unverified
    'SVI': 'scarletviolet',   # unverified
    'PAL': 'paldeaevolved',   # unverified
    'OBF': 'obsidianflames',  # unverified
    'PAR': 'paradoxrift',     # unverified
    'PAF': 'paldeanfates',    # unverified
    'TEF': 'temporalforces',  # unverified
    'TWM': 'twilightmasquerade',  # unverified
    'SFA': 'shroudedfable',   # unverified
    'SCR': 'stellarcrown',    # unverified
    'SSP': 'surgingsparks',   # unverified
    'PRE': 'prismaticevolutions',  # unverified
    'JTG': 'journeytogether',  # unverified
    'DRI': 'destinedrivals',  # unverified
}


def fetch_page(set_code, number):
    slug = SEREBII_SET_SLUGS.get(set_code)
    if not slug:
        return None, f"no slug mapping for {set_code}"
    # Confirmed 2026-07-13: the page URL is zero-padded 3 digits
    # (e.g. 048.shtml), unlike the image URL which is unpadded (48.jpg).
    padded = str(int(number)).zfill(3)
    url = f"https://www.serebii.net/card/{slug}/{padded}.shtml"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code} for {url}"
        return r.text, None
    except Exception as e:
        return None, str(e)


def parse_serebii_html(html):
    """
    Extraction built directly against CONFIRMED real HTML (Mega Darkrai ex,
    PBL #48, verified 2026-07-13). Ability pattern is still UNCONFIRMED --
    this specific test card had no ability, only the Pokemon-ex rule
    reminder text (which is correctly NOT captured as an ability below).
    Test against a card that DOES have an ability before trusting that
    one field.
    """
    result = {
        'name': '', 'hp': None, 'ability_name': '', 'ability_text': '',
        'attack_1_name': '', 'attack_1_damage': '', 'attack_1_text': '',
        'attack_2_name': '', 'attack_2_damage': '', 'attack_2_text': '',
        'weakness_type': '', 'weakness_value': '',
        'resistance_type': '', 'resistance_value': '',
        'retreat_cost': None, 'artist': '', 'pokedex_number': None,
        'card_subtypes': '', 'description': '',
    }

    def strip_tags(s):
        cleaned = html_module.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).strip())
        return cleaned.replace('\xa0', ' ').strip()

    # Try Pokemon-card name pattern first
    m = re.search(r'<td colspan="2" class="main"><b>(.*?)</b></td>', html, re.DOTALL)
    if m:
        result['name'] = strip_tags(m.group(1))
    else:
        # Trainer/Item/Supporter/Stadium layout -- confirmed against real
        # HTML (Backtrack Badge, PBL #74, 2026-07-13). Completely different
        # structure from Pokemon cards: no HP, no attacks, no weakness
        # table. Name + subtype come from one row; rules text from another.
        m = re.search(
            r'<td><b>([^<]+?)\s*</b></td><td[^>]*><div align="right"><i>([^<]+)</i></div></td>',
            html
        )
        if m:
            result['name'] = strip_tags(m.group(1))
            result['card_subtypes'] = strip_tags(m.group(2))

            # Rules text: the next <td colspan="3" align="left"> cell after the name row
            m2 = re.search(
                r'<td colspan="3" align="left">&nbsp;<p>\s*(.*?)\s*</td>',
                html, re.DOTALL
            )
            if m2:
                result['description'] = strip_tags(m2.group(1))

    # HP: <font color="#FF0000"><b>280 HP &nbsp;</b></font>
    m = re.search(r'<b>(\d+)\s*HP', html)
    if m:
        result['hp'] = int(m.group(1))

    # Attacks: each is a 3-cell row -- energy icons, name+text, damage.
    # Damage can be an empty <b></b> (e.g. status-only attacks like Abyss Eye).
    attack_pattern = re.compile(
        r'<td class="medium"><span class="main"><a[^>]*><b>([^<]+)</b></a></span><br>\s*'
        r'(.*?)</td>\s*<td colspan="2" align="center" class="main"><b>([^<]*)</b></td>',
        re.DOTALL
    )
    attacks = attack_pattern.findall(html)
    if len(attacks) >= 1:
        result['attack_1_name'] = attacks[0][0].strip()
        result['attack_1_text'] = strip_tags(attacks[0][1])
        result['attack_1_damage'] = attacks[0][2].strip()
    if len(attacks) >= 2:
        result['attack_2_name'] = attacks[1][0].strip()
        result['attack_2_text'] = strip_tags(attacks[1][1])
        result['attack_2_damage'] = attacks[1][2].strip()

    # Weakness: <b>Weakness</b></td> <td><img src=".../grass.png" ...>x2</td>
    m = re.search(
        r'<b>Weakness</b></td>\s*<td>(?:<img[^>]*src="[^"]*/([a-z]+)\.png"[^>]*>)?\s*(x\d+)?',
        html
    )
    if m and m.group(1):
        result['weakness_type'] = m.group(1).capitalize()
        result['weakness_value'] = m.group(2) or ''

    # Resistance: same shape as weakness, often empty (<td></td>) when no resistance
    m = re.search(
        r'<b>Resistance</b></td>\s*<td>(?:<img[^>]*src="[^"]*/([a-z]+)\.png"[^>]*>)?\s*(-\d+)?',
        html
    )
    if m and m.group(1):
        result['resistance_type'] = m.group(1).capitalize()
        result['resistance_value'] = m.group(2) or ''

    # Retreat cost: count of energy-icon <img> tags in the cell after "Retreat Cost"
    m = re.search(r'<b>Retreat Cost</b></td>\s*<td colspan="3">(.*?)</tr>', html, re.DOTALL)
    if m:
        result['retreat_cost'] = m.group(1).count('<img')

    # Illustrator: Illustration: <a href="..."><u>5ban Graphics</u></a>
    m = re.search(r'Illustration:\s*<a[^>]*><u>([^<]+)</u>', html)
    if m:
        result['artist'] = html_module.unescape(m.group(1).strip())

    # National Pokedex number -- confirmed present on regular Basic/Stage
    # cards ("NO. 0541  ...") but ABSENT on EX/secret-rare layout cards
    # like the one this was tested against -- blank here is expected, not
    # a bug, for that card type.
    m = re.search(r'NO\.\s*(\d+)', html)
    if m:
        result['pokedex_number'] = int(m.group(1))

    # Ability -- UNCONFIRMED, no test card with a real ability seen yet.
    # Best guess based on typical Serebii ability-row styling.
    m = re.search(r'[Aa]bility.*?<b>([^<]+)</b>\s*<br>\s*(.*?)</td>', html, re.DOTALL)
    if m:
        result['ability_name'] = m.group(1).strip()
        result['ability_text'] = strip_tags(m.group(2))

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("set_code", type=str, help="Set code, or ALL")
    parser.add_argument("number", type=str, nargs='?', help="Card number, required with --test-one")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--test-one", action="store_true", help="Fetch ONE card, print every field, save nothing")
    args = parser.parse_args()

    if args.test_one:
        if not args.number:
            print("Usage: python enrich_serebii.py --test-one SET_CODE NUMBER")
            sys.exit(1)
        html, err = fetch_page(args.set_code, args.number)
        if err:
            print(f"FAILED: {err}")
            sys.exit(1)
        print(f"Fetched {len(html)} bytes. Parsed fields:\n")
        parsed = parse_serebii_html(html)
        for k, v in parsed.items():
            print(f"  {k}: {v!r}")
        print("\nCheck every field above against the actual card before trusting this parser.")
        print("If anything is wrong/empty that should have a value, the regex needs adjusting")
        print("-- paste this output back along with what the real card actually shows.")
        return

    # Import here so --test-one works without Django DB access if run standalone.
    # This script runs as `python enrich_serebii.py`, not through manage.py shell,
    # so Django needs to be bootstrapped manually before any model import.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

    from django.db import transaction
    from products.models import PokemonProduct, CardSet

    set_code = args.set_code.upper()
    codes = list(CardSet.objects.values_list("code", flat=True)) if set_code == "ALL" else [set_code]

    for code in codes:
        slug = SEREBII_SET_SLUGS.get(code)
        if not slug:
            print(f"[{code}] no Serebii slug mapping -- skip")
            continue

        products = PokemonProduct.objects.filter(card_set__code=code, card_number__isnull=False)
        print(f"\n[{code}] -> serebii:{slug}  ({products.count()} DB rows)")

        matched = 0
        not_found = 0
        to_update = []

        seen_numbers = {}
        for p in products:
            if p.card_number in seen_numbers:
                seen_numbers[p.card_number].append(p)
                continue
            seen_numbers[p.card_number] = [p]

        for card_number, rows in seen_numbers.items():
            html, err = fetch_page(code, card_number)
            time.sleep(DELAY)
            if err:
                not_found += 1
                continue

            parsed = parse_serebii_html(html)
            if not parsed.get('name'):
                not_found += 1
                continue

            matched += 1
            if args.verify_only:
                continue

            for p in rows:
                # Only fill blanks -- never overwrite existing data
                if not p.hp and parsed['hp']:
                    p.hp = parsed['hp']
                if not p.artist and parsed['artist']:
                    p.artist = parsed['artist']
                if not p.pokedex_number and parsed['pokedex_number']:
                    p.pokedex_number = parsed['pokedex_number']
                if not p.ability_name and parsed['ability_name']:
                    p.ability_name = parsed['ability_name']
                    p.ability_text = parsed['ability_text']
                if not p.attack_1_name and parsed['attack_1_name']:
                    p.attack_1_name = parsed['attack_1_name']
                    p.attack_1_damage = parsed['attack_1_damage']
                    p.attack_1_text = parsed['attack_1_text']
                if not p.attack_2_name and parsed['attack_2_name']:
                    p.attack_2_name = parsed['attack_2_name']
                    p.attack_2_damage = parsed['attack_2_damage']
                    p.attack_2_text = parsed['attack_2_text']
                if not p.weakness_type and parsed['weakness_type']:
                    p.weakness_type = parsed['weakness_type']
                    p.weakness_value = parsed['weakness_value']
                if not p.resistance_type and parsed['resistance_type']:
                    p.resistance_type = parsed['resistance_type']
                    p.resistance_value = parsed['resistance_value']
                if not p.retreat_cost and parsed['retreat_cost']:
                    p.retreat_cost = parsed['retreat_cost']
                if not p.card_subtypes and parsed['card_subtypes']:
                    p.card_subtypes = parsed['card_subtypes']
                if not p.description and parsed['description']:
                    p.description = parsed['description']

                if args.dry_run:
                    print(f"  [DRY] #{card_number} {p.name[:30]} -> {parsed['name'][:30]}")
                else:
                    to_update.append(p)

        if to_update and not args.dry_run:
            FIELDS = [
                'hp', 'artist', 'pokedex_number', 'ability_name', 'ability_text',
                'attack_1_name', 'attack_1_damage', 'attack_1_text',
                'attack_2_name', 'attack_2_damage', 'attack_2_text',
                'weakness_type', 'weakness_value', 'resistance_type', 'resistance_value',
                'retreat_cost', 'card_subtypes', 'description',
            ]
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(to_update, FIELDS, batch_size=500)

        total = len(seen_numbers)
        match_pct = (matched / total * 100) if total else 0
        print(f"  Matched: {matched}/{total} ({match_pct:.0f}%) | Not found: {not_found}")


if __name__ == '__main__':
    main()
