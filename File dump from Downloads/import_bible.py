"""
PokéBulk SA — Bible Import Management Command
===============================================
Place in: products/management/commands/import_bible.py

Usage:
    python manage.py import_bible <path_to_final_csv> [--dry-run] [--update]

What this does:
    - Reads the final Bible CSV (_final.csv)
    - Creates/updates Era, CardSet, PokemonProduct records
    - One PokemonProduct row per Bible row (each row = one variant/price point)
    - Matches on tcgcsv_product_id (most reliable) or csv_sku fallback
    - --dry-run: reports what would happen without writing
    - --update: update existing records (default: skip existing)
"""

import csv
import os
import sys
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# ─── Rarity mapping: TCGCSV rarity strings → model choices ─────────────────

RARITY_MAP = {
    'common':                    'common',
    'uncommon':                  'uncommon',
    'rare':                      'rare',
    'holo rare':                 'holo_rare',
    'ultra rare':                'ultra_rare',
    'illustration rare':         'illustration_rare',
    'special illustration rare': 'special_illustration_rare',
    'hyper rare':                'hyper_rare',
    'secret rare':               'secret_rare',
    'double rare':               'ultra_rare',
    'shiny rare':                'secret_rare',
    'shiny holo rare':           'secret_rare',
    'shiny ultra rare':          'secret_rare',
    'rainbow rare':              'hyper_rare',
    'ace spec rare':             'ace_spec',
    'rare ace':                  'ace_spec',
    'prism rare':                'ultra_rare',
    'radiant rare':              'ultra_rare',
    'rare break':                'ultra_rare',
    'amazing rare':              'ultra_rare',
    'classic collection':        'ultra_rare',
    'mega hyper rare':           'mega_hyper_rare',
    'mega attack rare':          'mega_attack_rare',
    'black white rare':          'rare',
    'promo':                     'rare',
    'code card':                 'common',
}

# ─── Era mapping: set_code prefix → Era code ───────────────────────────────

ERA_MAP = {
    'BS': ('WotC', 'WotC Era'),
    'JU': ('WotC', 'WotC Era'),
    'FO': ('WotC', 'WotC Era'),
    'BS2': ('WotC', 'WotC Era'),
    'TR': ('WotC', 'WotC Era'),
    'LC': ('WotC', 'WotC Era'),
    'BSS': ('WotC', 'WotC Era'),
    'G1': ('WotC', 'WotC Era'),
    'G2': ('WotC', 'WotC Era'),
    'N1': ('WotC', 'WotC Era'),
    'N2': ('WotC', 'WotC Era'),
    'N3': ('WotC', 'WotC Era'),
    'N4': ('WotC', 'WotC Era'),
    'EX': ('WotC', 'WotC Era'),
    'AQ': ('WotC', 'WotC Era'),
    'SK': ('WotC', 'WotC Era'),
    'SI1': ('WotC', 'WotC Era'),
}

def get_era_code(set_code, era_name):
    """Derive era from era_name column."""
    era_name = era_name.strip()
    if not era_name:
        return ('UNK', 'Unknown')
    # Map common era names
    era_slug_map = {
        'WotC Base': ('WotC', 'WotC Era'),
        'E-Card': ('ECard', 'E-Card Era'),
        'EX': ('EX', 'EX Era'),
        'Diamond & Pearl': ('DP', 'Diamond & Pearl Era'),
        'HeartGold SoulSilver': ('HGSS', 'HeartGold SoulSilver Era'),
        'Black & White': ('BW', 'Black & White Era'),
        'XY': ('XY', 'XY Era'),
        'Sun & Moon': ('SM', 'Sun & Moon Era'),
        'Sword & Shield': ('SWSH', 'Sword & Shield Era'),
        'Scarlet & Violet': ('SV', 'Scarlet & Violet Era'),
        'Mega Evolution': ('MEG', 'Mega Evolution Era'),
        'Promo': ('PROMO', 'Promo'),
    }
    return era_slug_map.get(era_name, (era_name[:10].replace(' ', ''), era_name))


def safe_decimal(val, default=None):
    try:
        v = str(val).strip()
        if not v:
            return default
        return Decimal(v)
    except InvalidOperation:
        return default


def safe_int(val, default=None):
    try:
        v = str(val).strip().split('/')[0].strip()
        if not v:
            return default
        return int(v)
    except (ValueError, TypeError):
        return default


def parse_bool(val):
    return str(val).strip().lower() in ('true', '1', 'yes')


class Command(BaseCommand):
    help = 'Import the final Bible CSV into the database'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the final Bible CSV')
        parser.add_argument('--dry-run', action='store_true', help='Report without writing')
        parser.add_argument('--update', action='store_true', help='Update existing records')
        parser.add_argument('--limit', type=int, default=0, help='Only process N rows (for testing)')

    def handle(self, *args, **options):
        from products.models import Era, CardSet, PokemonProduct, Category

        csv_file = options['csv_file']
        dry_run = options['dry_run']
        do_update = options['update']
        limit = options['limit']

        if not os.path.exists(csv_file):
            raise CommandError(f'File not found: {csv_file}')

        self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Importing: {csv_file}')

        with open(csv_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if limit:
            rows = rows[:limit]

        self.stdout.write(f'Total rows: {len(rows)}')

        # Pre-fetch / create the "Pokemon Card" category
        card_category, _ = (None, None) if dry_run else Category.objects.get_or_create(
            slug='pokemon-card', defaults={'name': 'Pokemon Card'}
        )

        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }

        era_cache = {}
        set_cache = {}

        with transaction.atomic():
            for i, row in enumerate(rows):
                if i % 1000 == 0:
                    self.stdout.write(f'  [{i}/{len(rows)}]...')

                sid = transaction.savepoint() if not dry_run else None
                try:
                    # ── Era ──────────────────────────────────────────────
                    era_name_raw = row.get('era', '').strip()
                    era_code, era_full_name = get_era_code(row.get('set_code', ''), era_name_raw)

                    if era_code not in era_cache:
                        if not dry_run:
                            era_obj, _ = Era.objects.get_or_create(
                                code=era_code,
                                defaults={'name': era_full_name}
                            )
                            era_cache[era_code] = era_obj
                        else:
                            era_cache[era_code] = None

                    # ── CardSet ──────────────────────────────────────────
                    set_code = row.get('set_code', '').strip()
                    if set_code not in set_cache:
                        if not dry_run:
                            set_obj, _ = CardSet.objects.get_or_create(
                                code=set_code,
                                defaults={
                                    'name': row.get('set_name', set_code),
                                    'era': era_cache.get(era_code),
                                }
                            )
                            set_cache[set_code] = set_obj
                        else:
                            set_cache[set_code] = None

                    # ── Rarity ───────────────────────────────────────────
                    rarity_raw = row.get('rarity', '').strip().lower()
                    rarity = RARITY_MAP.get(rarity_raw, 'common')

                    # ── Variant → price field ────────────────────────────
                    variant = row.get('variant', '').strip()
                    pokebulk_zar = safe_decimal(row.get('pokebulk_zar'), Decimal('0'))
                    price = pokebulk_zar or Decimal('0')

                    # Assign variant-specific price field
                    price_fields = {
                        'Normal':          'price_normal',
                        'Holofoil':        'price_holo',
                        'Reverse Holofoil':'price_reverse_holo',
                        '1st Edition':     'price_first_edition',
                        'Poke Ball':       'price_pokeball',
                        'Master Ball':     'price_masterball',
                        'Friend Ball':     'price_friendball',
                        'Love Ball':       'price_loveball',
                        'Quick Ball':      'price_quickball',
                        'Dusk Ball':       'price_duskball',
                    }
                    variant_price_field = price_fields.get(variant)

                    # ── tcgcsv_product_id ────────────────────────────────
                    product_id = safe_int(row.get('product_id'))

                    # ── Legality ─────────────────────────────────────────
                    leg_std = row.get('legality_standard', '').strip().lower()
                    leg_exp = row.get('legality_expanded', '').strip().lower()

                    def parse_legal(val):
                        if val in ('legal', 'true', '1', 'yes'):
                            return True
                        if val in ('banned', 'false', '0', 'no'):
                            return False
                        return None

                    # ── Image ────────────────────────────────────────────
                    image_url = row.get('final_image_url', '').strip() or row.get('tcgplayer_image_url', '').strip()

                    # ── Merged fields (handle both merge script variants) ─
                    # Local merge script uses final_artist/final_pokedex/final_regulation_mark
                    # Cloud merge script uses artist/pokedex_numbers/regulation_mark
                    artist = (row.get('final_artist') or row.get('artist') or '').strip()[:200]
                    pokedex_raw = (row.get('final_pokedex') or row.get('pokedex_numbers') or '').strip()
                    regulation_mark = (row.get('final_regulation_mark') or row.get('regulation_mark') or '').strip()

                    # ── Build defaults dict ───────────────────────────────
                    defaults = {
                        'name':           row.get('name', '').strip(),
                        'csv_sku':        f"{set_code}-{row.get('number','').strip()}-{variant}",
                        'tcgcsv_product_id': product_id,
                        'card_set':       set_cache.get(set_code),
                        'category':       card_category,
                        'rarity':         rarity,
                        'artist':         artist,
                        'hp':             safe_int(row.get('hp')),
                        'image_url':      image_url[:500] if image_url else '',
                        'price':          price,
                        'legal_standard': parse_legal(leg_std),
                        'legal_expanded': parse_legal(leg_exp),
                        'legal_unlimited': True,
                        'is_active':      True,
                        'stock':          0,
                    }

                    # Card number (numeric part only)
                    number_raw = row.get('number', '').strip()
                    defaults['card_number'] = safe_int(number_raw)

                    # Pokedex (first number if pipe-separated)
                    if pokedex_raw:
                        defaults['pokedex_number'] = safe_int(pokedex_raw.split('|')[0])

                    # Variant-specific price
                    if variant_price_field:
                        defaults[variant_price_field] = price

                    if dry_run:
                        stats['created'] += 1
                        continue

                    # ── Upsert ────────────────────────────────────────────
                    lookup = {}
                    if product_id:
                        lookup['tcgcsv_product_id'] = product_id
                    else:
                        lookup['csv_sku'] = defaults['csv_sku']

                    existing = PokemonProduct.objects.filter(**lookup).first()

                    if existing:
                        if do_update:
                            for k, v in defaults.items():
                                if v is not None and v != '':
                                    setattr(existing, k, v)
                            existing.save()
                            stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        PokemonProduct.objects.create(**defaults)
                        stats['created'] += 1

                except Exception as e:
                    if sid:
                        transaction.savepoint_rollback(sid)
                    stats['errors'] += 1
                    self.stderr.write(f'  Error row {i} ({row.get("name","?")}): {e}')
                else:
                    if sid:
                        transaction.savepoint_commit(sid)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(f"""
{'='*50}
IMPORT {'(DRY RUN) ' if dry_run else ''}COMPLETE
{'='*50}
Created:  {stats['created']}
Updated:  {stats['updated']}
Skipped:  {stats['skipped']}
Errors:   {stats['errors']}
{'='*50}
"""))
