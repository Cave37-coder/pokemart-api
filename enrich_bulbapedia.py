"""
PokéBulk SA — Bulbapedia Enrichment Script (FINAL)
====================================================
RULE: Bulbapedia PRIMARY. pokemontcg.io FALLBACK ONLY.
      Maximum Bulbapedia coverage before fallback runs.

Usage:
    pip install requests
    python enrich_bulbapedia.py pokebulk_bible_cards_only_YYYYMMDD.csv

Resume-safe: saves progress every 100 cards.
Delete *_bulba_progress.json for a clean full run.
"""

import sys, csv, re, json, time, os, requests
from datetime import datetime

BULBA_API  = "https://bulbapedia.bulbagarden.net/w/api.php"
ARCH_API   = "https://archives.bulbagarden.net/w/api.php"
HEADERS    = {"User-Agent": "PokeBulkSA/1.0.0 (enquiries@pokebulk.co.za)"}
DELAY      = 0.12
SAVE_EVERY = 100
TIMEOUT    = 15

BULBA_COLUMNS = [
    'bulba_page_title', 'bulba_image_filename', 'bulba_image_url',
    'bulba_artist', 'bulba_pokedex_number', 'bulba_regulation_mark',
    'bulba_legality_standard', 'bulba_legality_expanded',
    'bulba_legality_unlimited', 'bulba_matched', 'bulba_match_method',
    'bulba_enriched_at',
]

BULBA_SET_NAMES = {
    'BS':'Base_Set','BSS':'Base_Set','JU':'Jungle','FO':'Fossil',
    'BS2':'Base_Set_2','TR':'Team_Rocket','G1':'Gym_Heroes','G2':'Gym_Challenge',
    'N1':'Neo_Genesis','N2':'Neo_Discovery','N3':'Neo_Revelation','N4':'Neo_Destiny',
    'LC':'Legendary_Collection','EX':'Expedition','AQ':'Aquapolis',
    'SK':'Skyridge','SI1':'Southern_Islands',
    'RS':'EX_Ruby_%26_Sapphire','SS':'EX_Sandstorm','DR':'EX_Dragon',
    'MA':'EX_Team_Magma_vs_Team_Aqua','HL':'EX_Hidden_Legends',
    'RG':'EX_FireRed_%26_LeafGreen','TRR':'EX_Team_Rocket_Returns',
    'DX':'EX_Deoxys','EM':'EX_Emerald','UF':'EX_Unseen_Forces',
    'DS':'EX_Delta_Species','LM':'EX_Legend_Maker','HP':'EX_Holon_Phantoms',
    'CG':'EX_Crystal_Guardians','DF':'EX_Dragon_Frontiers','PK':'EX_Power_Keepers',
    'DP':'Diamond_%26_Pearl','MT':'Mysterious_Treasures','SW':'Secret_Wonders',
    'GE':'Great_Encounters','MD':'Majestic_Dawn','LA':'Legends_Awakened',
    'SF':'Stormfront','PL':'Platinum','RR':'Rising_Rivals',
    'SV':'Supreme_Victors','AR':'Arceus',
    'HS':'HeartGold_%26_SoulSilver','UL':'Unleashed','UD':'Undaunted',
    'TM':'Triumphant','CoL':'Call_of_Legends',
    'BLW':'Black_%26_White','EPO':'Emerging_Powers','NVI':'Noble_Victories',
    'NXD':'Next_Destinies','DEX':'Dark_Explorers','DRX':'Dragons_Exalted',
    'DRV':'Dragon_Vault','BCR':'Boundaries_Crossed','PLS':'Plasma_Storm',
    'PLF':'Plasma_Freeze','PLB':'Plasma_Blast','LTR':'Legendary_Treasures',
    'KSS':'Kalos_Starter_Set','XY':'XY','FLF':'Flashfire','FFI':'Furious_Fists',
    'PHF':'Phantom_Forces','PRC':'Primal_Clash','DCR':'Double_Crisis',
    'ROS':'Roaring_Skies','AOR':'Ancient_Origins','BKT':'BREAKthrough',
    'BKP':'BREAKpoint','GEN':'Generations','FCO':'Fates_Collide',
    'STS':'Steam_Siege','EVO':'Evolutions',
    'SHL':'Shining_Legends','SM01':'Sun_%26_Moon','SM02':'Guardians_Rising',
    'SM03':'Burning_Shadows','SM04':'Crimson_Invasion','SM05':'Ultra_Prism',
    'SM06':'Forbidden_Light','CES':'Celestial_Storm','DRM':'Dragon_Majesty',
    'SM8':'Lost_Thunder','SM9':'Team_Up','SM10':'Unbroken_Bonds',
    'SM11':'Unified_Minds','HIF':'Hidden_Fates','HIFSV':'Hidden_Fates',
    'SM12':'Cosmic_Eclipse',
    'SHF':'Shining_Fates','SHFSV':'Shining_Fates',
    'SWSH01':'Sword_%26_Shield','SWSH02':'Rebel_Clash','SWSH03':'Darkness_Ablaze',
    'CHP':"Champion%27s_Path",'SWSH04':'Vivid_Voltage','SWSH05':'Battle_Styles',
    'SWSH06':'Chilling_Reign','SWSH07':'Evolving_Skies',
    'CLB':'Celebrations','CCC':'Celebrations',
    'SWSH08':'Fusion_Strike','SWSH09':'Brilliant_Stars','BST':'Brilliant_Stars',
    'SWSH10':'Astral_Radiance','ASRTG':'Astral_Radiance',
    'PGO':'Pok%C3%A9mon_GO',
    'SWSH11':'Lost_Origin','LORTG':'Lost_Origin',
    'SWSH12':'Silver_Tempest','ST':'Silver_Tempest',
    'CRZ':'Crown_Zenith','CRZGG':'Crown_Zenith',
    'SVI':'Scarlet_%26_Violet','SVE':'Scarlet_%26_Violet_Energies',
    'PAL':'Paldea_Evolved','OBF':'Obsidian_Flames','MEW':'151',
    'PAR':'Paradox_Rift','PAF':'Paldean_Fates','TEF':'Temporal_Forces',
    'TWM':'Twilight_Masquerade','SFA':'Shrouded_Fable','SCR':'Stellar_Crown',
    'SSP':'Surging_Sparks','PRE':'Prismatic_Evolutions',
    'JTG':'Journey_Together','DRI':'Destined_Rivals',
    'BLK':'Black_Bolt','WHT':'White_Flare',
    'SVP':'Scarlet_%26_Violet_Black_Star_Promos',
    'MEG':'Mega_Evolution','PFL':'Phantasmal_Flames','ASC':'Ascended_Heroes',
    'POR':'Perfect_Order','CRI':'Chaos_Rising','PBL':'Pitch_Black','ME05':'Pitch_Black',
    'MEP':'Mega_Evolution_Promo','MEE':'Mega_Evolution_Energies',
    'PRIZEPACK':'Prize_Pack_Series',
    'TK1':'Trick_or_Trade','TK2':'Trick_or_Trade_2023','TK24':'Trick_or_Trade_2024',
}

# ── NAME CLEANER (COMPLETE) ───────────────────────────────────────────────────

def clean_name(name):
    """
    Clean TCGCSV card name for Bulbapedia page title construction.
    Handles ALL known TCGCSV naming edge cases.
    Returns (cleaned_name, is_delta) tuple.
    """
    # Detect Delta Species BEFORE stripping anything
    is_delta = '(Delta Species' in name

    # Strip TCGCSV disambiguation suffix " - N/total" or " - 0N/total"
    name = re.sub(r'\s*-\s*0*\d+[a-z]?/\d+\s*$', '', name).strip()
    name = re.sub(r'\s*-\s*0*\d+\s*$', '', name).strip()

    # Strip ALL Delta Species variants (forme info etc.)
    name = re.sub(r'\s*\(Delta Species[^)]*\)\s*', '', name).strip()

    # Ho-oh capitalisation fix (Bulbapedia uses Ho-Oh)
    name = name.replace('Ho-oh', 'Ho-Oh')

    # M [Name] EX → Mega [Name]-EX
    m_ex = re.match(r'^M\s+(.+?)\s+EX$', name)
    if m_ex:
        name = f"Mega {m_ex.group(1)}-EX"

    # Strip role/type descriptors in parentheses
    for pattern in [
        r'\s*\(Supporter\)\s*$', r'\s*\(Trainer\)\s*$',
        r'\s*\(Item\)\s*$',      r'\s*\(Stadium\)\s*$',
        r'\s*\(Prime\)\s*$',     r'\s*\(Basic\)\s*$',
        r'\s*\(Special\)\s*$',   r'\s*\(Secret\)\s*$',
        r'\s*\(Secret Rare\)\s*$',
    ]:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()

    # Vivillon form name — strip everything in parens
    if name.startswith('Vivillon'):
        name = re.sub(r'\s*\(.*\)\s*$', '', name).strip()

    # Unown letter in parens: "Unown (A)" → "Unown A" (BEFORE disambiguation strip)
    name = re.sub(r'^(Unown)\s*\(([A-Z!?])\)\s*$', r'\1 \2', name)

    # Strip disambiguation: pure numbers OR number+letter (74a, 95a)
    name = re.sub(r'\s*\(\d+[a-z]?\)\s*$', '', name).strip()

    # Strip AR disambiguation: (AR1), (AR2)
    name = re.sub(r'\s*\(AR\d+\)\s*$', '', name).strip()

    # Strip holo disambiguation: (H1)
    name = re.sub(r'\s*\(H\d+\)\s*$', '', name).strip()

    # Strip (Shiny) — SH number handles this
    name = re.sub(r'\s*\(Shiny\)\s*$', '', name, flags=re.IGNORECASE).strip()

    # Strip secret/full art count suffixes: "(104 Secret Rare)", "(97 Full Art)"
    name = re.sub(
        r'\s*\(\d+\s+(?:Full Art|Secret Rare|Secret|Shiny)\)\s*$',
        '', name, flags=re.IGNORECASE
    ).strip()

    # Strip affiliation tags
    name = re.sub(r'\s*\(Team Plasma\)\s*$', '', name).strip()
    name = re.sub(r'\s*\(E4\)\s*$', '', name).strip()

    # Nidoran gender symbols
    name = name.replace('Nidoran F', 'Nidoran♀')
    name = name.replace('Nidoran M', 'Nidoran♂')

    # Unown bracket notation: [E] → E
    name = re.sub(r'\s*\[([A-Z!?])\]\s*', r' \1', name).strip()

    # Lv.X / LV.X suffix
    name = re.sub(r'\s+Lv\.X$', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s+LV\.X$', '', name, flags=re.IGNORECASE).strip()

    return name, is_delta


# ── NUMBER CLEANER ────────────────────────────────────────────────────────────

def clean_number(number_raw):
    """Extract card number for Bulbapedia page title."""
    num = str(number_raw).split('/')[0].strip()

    # Letter-suffixed numbers: 074a → 74, 095b → 95
    m = re.match(r'^0*(\d+)[a-z]$', num)
    if m:
        return str(int(m.group(1)))

    # SH, RT, TG, GG — strip leading zeros: SH01→SH1
    m = re.match(r'^(SH|RT|TG|GG)0*(\d+)$', num)
    if m:
        return f"{m.group(1)}{m.group(2)}"

    # H prefix: H01→H1
    m = re.match(r'^H0*(\d+)$', num)
    if m:
        return f"H{m.group(1)}"

    # AR prefix: AR1, AR2
    if re.match(r'^AR\d+$', num):
        return num

    # Unown letter: A, B, !, ?
    if re.match(r'^[A-Z!?]$', num):
        return num

    # Promo codes: SWSH001
    if re.match(r'^[A-Z]{2,}\d+$', num):
        return num

    # Standard: strip leading zeros
    if num.isdigit():
        return str(int(num))

    return num


# ── URL BUILDER ───────────────────────────────────────────────────────────────

def name_to_url(name):
    """Convert cleaned name to Bulbapedia URL fragment."""
    return (name
            .replace(' ', '_')
            .replace("'", '%27')
            .replace('&', '%26')
            .replace('[', '').replace(']', '')
            .replace(':', ''))


def build_titles(name_raw, set_code, number_raw):
    """Build ordered list of Bulbapedia page titles to try."""
    set_name = BULBA_SET_NAMES.get(set_code)
    if not set_name:
        return []

    name, is_delta = clean_name(name_raw)
    num            = clean_number(number_raw)
    url_name       = name_to_url(name)

    titles = []

    if is_delta:
        # Delta Species cards use δ symbol in Bulbapedia page titles
        # Primary: Name_δ_(Set_Num)
        delta_url = url_name + '_%CE%B4'  # δ URL-encoded
        titles.append(f"{delta_url}_({set_name}_{num})")
        # Fallback: without δ (some sets like CG don't use it)
        titles.append(f"{url_name}_({set_name}_{num})")
        # Fallback: without number
        titles.append(f"{delta_url}_({set_name})")
    else:
        # Standard card
        titles.append(f"{url_name}_({set_name}_{num})")
        # Fallback: without number
        titles.append(f"{url_name}_({set_name})")
        # Fallback: with accented é
        if 'e' in name and 'é' not in name:
            accented = name.replace('e', 'é', 1)
            titles.append(f"{name_to_url(accented)}_({set_name}_{num})")

    return titles


# ── API CALLS ─────────────────────────────────────────────────────────────────

def fetch_wikitext(page_title, _redirect_depth=0):
    """
    Fetch raw wikitext for a Bulbapedia page.
    Automatically follows #REDIRECT pages (e.g. BS2/LC reprints → original set page).
    Max redirect depth: 2 to avoid loops.
    """
    if _redirect_depth > 2:
        return None, True

    query_title = (page_title
                   .replace('_', ' ').replace('%26', '&').replace('%27', "'")
                   .replace('%C3%A9', 'é').replace('%E2%99%80', '♀')
                   .replace('%E2%99%82', '♂'))
    params = {
        'action': 'query', 'prop': 'revisions', 'rvprop': 'content',
        'rvslots': 'main', 'titles': query_title,
        'format': 'json', 'formatversion': '2',
    }
    try:
        r = requests.get(BULBA_API, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, True
        data  = r.json()
        pages = data.get('query', {}).get('pages', [])
        if not pages or pages[0].get('missing'):
            return None, True
        revs = pages[0].get('revisions', [])
        if not revs:
            return None, True
        content = revs[0].get('slots', {}).get('main', {}).get('content', '')

        # Follow redirects — common for reprints (BS2, LC redirect to original set)
        if content.strip().upper().startswith('#REDIRECT'):
            import re as _re
            m = _re.search(r'#[Rr][Ee][Dd][Ii][Rr][Ee][Cc][Tt]\s*\[\[(.+?)(?:\|.+?)?\]\]', content)
            if m:
                target = m.group(1).strip().replace(' ', '_')
                time.sleep(DELAY)
                return fetch_wikitext(target, _redirect_depth + 1)
            return None, True

        return content, False
    except Exception:
        return None, True


def resolve_image_url(filename):
    params = {
        'action': 'query', 'titles': f'File:{filename}',
        'prop': 'imageinfo', 'iiprop': 'url',
        'format': 'json', 'formatversion': '2',
    }
    try:
        r = requests.get(ARCH_API, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return ''
        data  = r.json()
        pages = data.get('query', {}).get('pages', [])
        if not pages or pages[0].get('missing'):
            return ''
        info = pages[0].get('imageinfo', [])
        return info[0].get('url', '') if info else ''
    except Exception:
        return ''


# ── WIKITEXT PARSER ───────────────────────────────────────────────────────────

def parse_wikitext(wikitext):
    result = {
        'bulba_image_filename': '', 'bulba_artist': '',
        'bulba_pokedex_number': '', 'bulba_regulation_mark': '',
        'bulba_legality_standard': '', 'bulba_legality_expanded': '',
        'bulba_legality_unlimited': '',
    }
    m = re.search(r'\|image\s*=\s*([^\n|{}]+\.(?:jpg|png|gif))', wikitext, re.IGNORECASE)
    if m:
        result['bulba_image_filename'] = m.group(1).strip()
    m = re.search(r'\|illus(?:trator)?\s*=\s*([^\n|{}]+)', wikitext)
    if m:
        result['bulba_artist'] = m.group(1).strip()
    m = re.search(r'\|ndex\s*=\s*(\d+)', wikitext)
    if m:
        result['bulba_pokedex_number'] = str(int(m.group(1)))
    m = re.search(r'\|regulation\s*=\s*([A-Z])', wikitext)
    if m:
        result['bulba_regulation_mark'] = m.group(1)
    if re.search(r'standard.*?[Ll]egal', wikitext):
        result['bulba_legality_standard'] = 'Legal'
    if re.search(r'expanded.*?[Ll]egal', wikitext):
        result['bulba_legality_expanded'] = 'Legal'
    if re.search(r'unlimited.*?[Ll]egal', wikitext):
        result['bulba_legality_unlimited'] = 'Legal'
    return result


# ── CARD ENRICHMENT ───────────────────────────────────────────────────────────

def enrich_card(name_raw, set_code, number_raw):
    empty = {c: '' for c in BULBA_COLUMNS}
    empty['bulba_matched']     = 'False'
    empty['bulba_enriched_at'] = datetime.now().isoformat(timespec='seconds')

    titles = build_titles(name_raw, set_code, number_raw)
    if not titles:
        empty['bulba_match_method'] = 'no_set_mapping'
        return empty

    for i, title in enumerate(titles):
        wikitext, missing = fetch_wikitext(title)
        time.sleep(DELAY)
        if missing or not wikitext:
            continue
        parsed    = parse_wikitext(wikitext)
        image_url = ''
        if parsed['bulba_image_filename']:
            image_url = resolve_image_url(parsed['bulba_image_filename'])
            time.sleep(DELAY)
        return {
            'bulba_page_title':         title,
            'bulba_image_filename':     parsed['bulba_image_filename'],
            'bulba_image_url':          image_url,
            'bulba_artist':             parsed['bulba_artist'],
            'bulba_pokedex_number':     parsed['bulba_pokedex_number'],
            'bulba_regulation_mark':    parsed['bulba_regulation_mark'],
            'bulba_legality_standard':  parsed['bulba_legality_standard'],
            'bulba_legality_expanded':  parsed['bulba_legality_expanded'],
            'bulba_legality_unlimited': parsed['bulba_legality_unlimited'],
            'bulba_matched':            'True',
            'bulba_match_method':       f'attempt_{i+1}',
            'bulba_enriched_at':        datetime.now().isoformat(timespec='seconds'),
        }

    empty['bulba_page_title']   = titles[0] if titles else ''
    empty['bulba_match_method'] = 'not_found'
    return empty


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python enrich_bulbapedia.py <bible_cards_csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    base, ext       = os.path.splitext(input_file)
    output_file     = f"{base}_bulba_enriched{ext}"
    progress_file   = f"{base}_bulba_progress.json"

    print("=" * 65)
    print("PokéBulk SA — Bulbapedia Enrichment (FINAL CLEAN RUN)")
    print("=" * 65)
    print(f"Input:    {input_file}")
    print(f"Output:   {output_file}")
    print(f"Progress: {progress_file}")
    print()

    enriched_cache = {}
    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            enriched_cache = json.load(f)
        print(f"Resuming: {len(enriched_cache)} cards already in cache")
    else:
        print("Fresh run — no cache found")
    print()

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        input_fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"Total rows: {len(rows)}")

    output_fieldnames = list(input_fieldnames)
    for col in BULBA_COLUMNS:
        if col not in output_fieldnames:
            output_fieldnames.append(col)

    seen = set()
    unique_cards = []
    for row in rows:
        key = (row['name'], row['set_code'], row['number'])
        if key not in seen:
            seen.add(key)
            unique_cards.append(key)

    already    = sum(1 for k in unique_cards if str(k) in enriched_cache)
    remaining  = len(unique_cards) - already
    print(f"Unique cards: {len(unique_cards)} | Done: {already} | Remaining: {remaining}")
    print()

    stats = {'matched': 0, 'not_found': 0, 'no_mapping': 0}

    for i, (name, set_code, number) in enumerate(unique_cards):
        cache_key = str((name, set_code, number))
        if cache_key in enriched_cache:
            continue

        print(
            f"[{i+1}/{len(unique_cards)}] "
            f"{set_code:8} #{number:12} {name[:28]:<28}",
            end=' ', flush=True
        )

        bulba  = enrich_card(name, set_code, number)
        enriched_cache[cache_key] = bulba
        matched = bulba.get('bulba_matched') == 'True'
        method  = bulba.get('bulba_match_method', '')

        if matched:
            img = '✓ img' if bulba.get('bulba_image_url') else '✓ no_img'
            print(f"{img} | {bulba.get('bulba_artist','')[:20]}")
            stats['matched'] += 1
        elif method == 'no_set_mapping':
            print('SKIP (no set mapping)')
            stats['no_mapping'] += 1
        else:
            print('NOT FOUND')
            stats['not_found'] += 1

        if (i + 1) % SAVE_EVERY == 0:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(enriched_cache, f)
            print(f"  → Progress saved ({i+1}/{len(unique_cards)})")

    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(enriched_cache, f)

    print(f"\nWriting: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        for row in rows:
            cache_key = str((row['name'], row['set_code'], row['number']))
            bulba     = enriched_cache.get(cache_key, {c: '' for c in BULBA_COLUMNS})
            out_row   = dict(row)
            for col in BULBA_COLUMNS:
                out_row[col] = bulba.get(col, '')
            writer.writerow(out_row)

    total = len(unique_cards)
    print(f"""
{'='*65}
ENRICHMENT COMPLETE
{'='*65}
Unique cards:  {total}
  Matched:     {stats['matched']} ({stats['matched']/max(total,1)*100:.1f}%)
  Not found:   {stats['not_found']}
  No mapping:  {stats['no_mapping']}

Output: {output_file}

NEXT — only after reviewing match rate:
  python enrich_ptcg_fallback.py {output_file}
{'='*65}
""")

if __name__ == '__main__':
    main()
