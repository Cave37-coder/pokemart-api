"""
PokéBulk SA — pokemontcg.io Fallback Enrichment
=================================================
Run AFTER enrich_bulbapedia.py.

Usage:
    python enrich_ptcg_fallback.py pokebulk_bible_cards_only_YYYYMMDD_bulba_enriched.csv

What this does:
    - Reads the Bulbapedia-enriched CSV
    - For cards where bulba_image_url is BLANK: queries pokemontcg.io GitHub data
    - Fills ptcg_ columns ONLY — never touches TCGCSV or bulba_ columns
    - Uses GitHub raw JSON files (no API key needed, no rate limits)

Adds these columns:
    ptcg_set_id         — pokemontcg.io set ID (e.g. swsh6)
    ptcg_card_id        — pokemontcg.io card ID (e.g. swsh6-57)
    ptcg_image_small    — small image URL
    ptcg_image_large    — large image URL (preferred)
    ptcg_artist         — artist name from pokemontcg.io
    ptcg_regulation_mark— regulation mark
    ptcg_pokedex        — national pokedex numbers (pipe-separated)
    ptcg_matched        — True/False
"""

import sys
import csv
import os
import json
import time
import requests

HEADERS = {"User-Agent": "PokeBulkSA/1.0.0"}
GITHUB_BASE = "https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master/cards/en"
DELAY = 0.05

PTCG_COLUMNS = [
    'ptcg_set_id',
    'ptcg_card_id',
    'ptcg_image_small',
    'ptcg_image_large',
    'ptcg_artist',
    'ptcg_regulation_mark',
    'ptcg_pokedex',
    'ptcg_matched',
]

# Our set code → pokemontcg.io set ID
CODE_TO_PTCG = {
    'BS':'base1','JU':'base2','FO':'base3','BS2':'base4','TR':'base5',
    'LC':'base6','BSS':'basep','G1':'gym1','G2':'gym2',
    'N1':'neo1','N2':'neo2','N3':'neo3','N4':'neo4',
    'EX':'ecard1','AQ':'ecard2','SK':'ecard3','SI1':'si1',
    'RS':'ex1','SS':'ex2','DR':'ex3','MA':'ex4','HL':'ex5',
    'RG':'ex6','TRR':'ex7','DX':'ex8','EM':'ex9','UF':'ex10',
    'DS':'ex11','LM':'ex12','HP':'ex13','CG':'ex14','DF':'ex15','PK':'ex16',
    'DP':'dp1','MT':'dp2','SW':'dp3','GE':'dp4','MD':'dp5',
    'LA':'dp6','SF':'dp7','PL':'pl1','RR':'pl2','SV':'pl3','AR':'pl4',
    'HS':'hgss1','UL':'hgss2','UD':'hgss3','TM':'hgss4','CoL':'col1',
    'BLW':'bw1','EPO':'bw2','NVI':'bw3','NXD':'bw4','DEX':'bw5',
    'DRX':'bw6','DRV':'dv1','BCR':'bw7','PLS':'bw8','PLF':'bw9',
    'PLB':'bw10','LTR':'bw11',
    'KSS':'xy0','XY':'xy1','FLF':'xy2','FFI':'xy3','PHF':'xy4',
    'PRC':'xy5','DCR':'dc1','ROS':'xy6','AOR':'xy7','BKT':'xy8',
    'BKP':'xy9','GEN':'g1','FCO':'xy10','STS':'xy11','EVO':'xy12',
    'SHL':'sm35','SM01':'sm1','SM02':'sm2','SM03':'sm3','SM04':'sm4',
    'SM05':'sm5','SM06':'sm6','CES':'sm7','DRM':'sm75','SM8':'sm8',
    'SM9':'sm9','SM10':'sm10','SM11':'sm11','HIF':'sm115','HIFSV':'sma',
    'SM12':'sm12',
    'SHF':'swsh45','SHFSV':'swsh45sv',
    'SWSH01':'swsh1','SWSH02':'swsh2','SWSH03':'swsh3','SWSH04':'swsh4',
    'SWSH05':'swsh5','SWSH06':'swsh6','SWSH07':'swsh7','SWSH08':'swsh8',
    'SWSH09':'swsh9','BST':'swsh9tg',
    'SWSH10':'swsh10','ASRTG':'swsh10tg',
    'SWSH11':'swsh11','LORTG':'swsh11tg',
    'SWSH12':'swsh12','ST':'swsh12tg',
    'CLB':'cel25','CCC':'cel25c',
    'CHP':'swsh35','PGO':'pgo',
    'CRZ':'swsh12pt5','CRZGG':'swsh12pt5gg',
    'SVP':'svp','SVE':'sve',
    'SVI':'sv1','PAL':'sv2','OBF':'sv3','MEW':'sv3pt5',
    'PAR':'sv4','PAF':'sv4pt5','TEF':'sv5','TWM':'sv6',
    'SFA':'sv6pt5','SCR':'sv7','SSP':'sv8','PRE':'sv8pt5',
    'JTG':'sv9','DRI':'sv10',
    'BLK':'zsv10pt5','WHT':'rsv10pt5',
    'MEG':'me1','PFL':'me2','ASC':'me2pt5','POR':'me3','CRI':'me4',
}

# Cache of loaded set data: ptcg_set_id → list of cards
_set_cache = {}

def load_ptcg_set(ptcg_id):
    """Load card data for a pokemontcg.io set from GitHub."""
    if ptcg_id in _set_cache:
        return _set_cache[ptcg_id]

    url = f"{GITHUB_BASE}/{ptcg_id}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            cards = r.json()
            _set_cache[ptcg_id] = cards
            time.sleep(DELAY)
            return cards
    except Exception as e:
        print(f"    Error loading {ptcg_id}: {e}")
    _set_cache[ptcg_id] = []
    return []


def find_ptcg_card(name, set_code, number_raw):
    """Find a card in pokemontcg.io data by name + number."""
    ptcg_id = CODE_TO_PTCG.get(set_code)
    if not ptcg_id:
        return None

    cards = load_ptcg_set(ptcg_id)
    if not cards:
        return None

    num = str(number_raw).split('/')[0].strip()
    num_int = str(int(num)) if num.isdigit() else num

    # Match by number first (most reliable)
    for card in cards:
        card_num = str(card.get('number', ''))
        if card_num == num or card_num == num_int or card_num == num.lstrip('0') or card_num.lstrip('0') == num_int:
            return card

    # Fallback: match by name + approximate number
    name_lower = name.lower().strip()
    for card in cards:
        if card.get('name', '').lower().strip() == name_lower:
            return card

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python enrich_ptcg_fallback.py <bulba_enriched_csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_ptcg_enriched{ext}"

    print("=" * 60)
    print("PokéBulk SA — pokemontcg.io Fallback Enrichment")
    print("=" * 60)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Note:   Only enriches cards where bulba_image_url is blank")
    print()

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        input_fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"Total rows: {len(rows)}")

    output_fieldnames = list(input_fieldnames)
    for col in PTCG_COLUMNS:
        if col not in output_fieldnames:
            output_fieldnames.append(col)

    # Find unique cards needing PTCG enrichment
    seen = set()
    ptcg_cache = {}
    stats = {'matched': 0, 'not_found': 0, 'skipped': 0, 'no_mapping': 0}

    unique_cards = []
    for row in rows:
        key = (row['name'], row['set_code'], row['number'])
        if key not in seen:
            seen.add(key)
            # Only enrich if bulba_image_url is blank
            if not row.get('bulba_image_url', '').strip():
                unique_cards.append(key)

    print(f"Cards needing PTCG enrichment: {len(unique_cards)}")
    print()

    for i, (name, set_code, number) in enumerate(unique_cards):
        print(f"[{i+1}/{len(unique_cards)}] {set_code} #{number} {name}...", end=' ')

        ptcg_id = CODE_TO_PTCG.get(set_code)
        if not ptcg_id:
            print("SKIP (no PTCG mapping)")
            ptcg_cache[(name, set_code, number)] = {'ptcg_matched': 'False'}
            stats['no_mapping'] += 1
            continue

        card = find_ptcg_card(name, set_code, number)

        if card:
            ptcg_cache[(name, set_code, number)] = {
                'ptcg_set_id':          ptcg_id,
                'ptcg_card_id':         card.get('id', ''),
                'ptcg_image_small':     card.get('images', {}).get('small', ''),
                'ptcg_image_large':     card.get('images', {}).get('large', ''),
                'ptcg_artist':          card.get('artist', ''),
                'ptcg_regulation_mark': card.get('regulationMark', ''),
                'ptcg_pokedex':         '|'.join(str(n) for n in card.get('nationalPokedexNumbers', [])),
                'ptcg_matched':         'True',
            }
            print(f"✓ {card.get('images', {}).get('large', '')[:40]}")
            stats['matched'] += 1
        else:
            ptcg_cache[(name, set_code, number)] = {'ptcg_matched': 'False'}
            print('NOT FOUND')
            stats['not_found'] += 1

    # Write output
    print(f"\nWriting: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()

        for row in rows:
            key = (row['name'], row['set_code'], row['number'])
            ptcg_data = ptcg_cache.get(key, {})

            out_row = dict(row)
            for col in PTCG_COLUMNS:
                out_row[col] = ptcg_data.get(col, '')

            writer.writerow(out_row)

    print(f"""
{'='*60}
PTCG FALLBACK ENRICHMENT COMPLETE
{'='*60}
Cards enriched:     {stats['matched']}
Not found:          {stats['not_found']}
No mapping:         {stats['no_mapping']}

Output: {output_file}

NEXT STEP:
  python merge_final_image.py {output_file}
{'='*60}
""")


if __name__ == '__main__':
    main()
