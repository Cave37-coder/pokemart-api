"""
PokéBulk SA — Final Image Merge
================================
Run AFTER both enrichment scripts.

Usage:
    python merge_final_image.py pokebulk_bible_cards_only_YYYYMMDD_bulba_enriched_ptcg_enriched.csv

What this does:
    - Reads the fully enriched CSV
    - Computes final_ columns by picking the best available source:

        final_image_url:
          1. bulba_image_url          (Bulbapedia Archives — highest quality)
          2. ptcg_image_large         (pokemontcg.io hi-res)
          3. tcgplayer_image_url      (TCGPlayer CDN — always available)

        final_artist:
          1. bulba_artist             (Bulbapedia — most accurate)
          2. ptcg_artist              (pokemontcg.io fallback)

        final_pokedex:
          1. bulba_pokedex_number     (Bulbapedia)
          2. ptcg_pokedex             (pokemontcg.io)

        final_regulation_mark:
          1. bulba_regulation_mark    (Bulbapedia)
          2. ptcg_regulation_mark     (pokemontcg.io)

        final_image_source:           which source was used (for audit)

    - NEVER modifies TCGCSV, bulba_, or ptcg_ columns
    - Outputs the complete master Bible CSV ready for import

This final CSV IS the Bible. Import it into Django.
"""

import sys
import csv
import os

FINAL_COLUMNS = [
    'final_image_url',
    'final_image_source',
    'final_artist',
    'final_pokedex',
    'final_regulation_mark',
]


def best(primary, *fallbacks):
    """Return first non-empty value."""
    for val in [primary, *fallbacks]:
        if val and str(val).strip():
            return str(val).strip()
    return ''


def main():
    if len(sys.argv) < 2:
        print("Usage: python merge_final_image.py <enriched_csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_FINAL{ext}"

    print("=" * 60)
    print("PokéBulk SA — Final Merge")
    print("=" * 60)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print()

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        input_fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"Total rows: {len(rows)}")

    output_fieldnames = list(input_fieldnames)
    for col in FINAL_COLUMNS:
        if col not in output_fieldnames:
            output_fieldnames.append(col)

    stats = {
        'bulba_image': 0,
        'ptcg_image':  0,
        'tcgp_image':  0,
        'no_image':    0,
    }

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()

        for row in rows:
            bulba_img = row.get('bulba_image_url', '').strip()
            ptcg_img  = row.get('ptcg_image_large', '').strip()
            tcgp_img  = row.get('tcgplayer_image_url', '').strip()

            if bulba_img:
                final_img = bulba_img
                source = 'bulbapedia'
                stats['bulba_image'] += 1
            elif ptcg_img:
                final_img = ptcg_img
                source = 'pokemontcg_io'
                stats['ptcg_image'] += 1
            elif tcgp_img:
                final_img = tcgp_img
                source = 'tcgplayer'
                stats['tcgp_image'] += 1
            else:
                final_img = ''
                source = 'none'
                stats['no_image'] += 1

            out_row = dict(row)
            out_row['final_image_url']       = final_img
            out_row['final_image_source']    = source
            out_row['final_artist']          = best(
                row.get('bulba_artist'),
                row.get('ptcg_artist'),
            )
            out_row['final_pokedex']         = best(
                row.get('bulba_pokedex_number'),
                row.get('ptcg_pokedex'),
            )
            out_row['final_regulation_mark'] = best(
                row.get('bulba_regulation_mark'),
                row.get('ptcg_regulation_mark'),
            )

            writer.writerow(out_row)

    total = len(rows)
    print(f"""
{'='*60}
FINAL MERGE COMPLETE
{'='*60}
Total rows:          {total}

Image sources:
  Bulbapedia:        {stats['bulba_image']} ({stats['bulba_image']/total*100:.1f}%)
  pokemontcg.io:     {stats['ptcg_image']} ({stats['ptcg_image']/total*100:.1f}%)
  TCGPlayer CDN:     {stats['tcgp_image']} ({stats['tcgp_image']/total*100:.1f}%)
  No image:          {stats['no_image']} ({stats['no_image']/total*100:.1f}%)

Output: {output_file}

THIS IS YOUR MASTER BIBLE CSV.
{'='*60}

Column structure summary:
  TCGCSV columns (pricing master — never modified):
    group_id, set_code, era, set_name, product_id, name, number,
    rarity, card_type, hp, stage, variant,
    market_usd, low_usd, pokebulk_zar, usd_zar_rate,
    tcgplayer_image_url, tcgplayer_url

  Bulbapedia columns (enrichment — separate):
    bulba_page_title, bulba_image_filename, bulba_image_url,
    bulba_artist, bulba_pokedex_number, bulba_regulation_mark,
    bulba_legality_*, bulba_matched, bulba_match_method

  pokemontcg.io columns (fallback — separate):
    ptcg_set_id, ptcg_card_id, ptcg_image_small, ptcg_image_large,
    ptcg_artist, ptcg_regulation_mark, ptcg_pokedex, ptcg_matched

  Final merged columns (used by Django/site):
    final_image_url, final_image_source,
    final_artist, final_pokedex, final_regulation_mark
""")


if __name__ == '__main__':
    main()
