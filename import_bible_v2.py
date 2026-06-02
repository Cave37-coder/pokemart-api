"""
PokéBulk SA — Bible Import Management Command
Place in: products/management/commands/import_bible.py
Usage:
    python manage.py import_bible <csv> [--dry-run] [--update] [--limit N]
"""

import csv
import os
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

RARITY_MAP = {
    'common': 'common', 'uncommon': 'uncommon', 'rare': 'rare',
    'holo rare': 'holo_rare', 'ultra rare': 'ultra_rare',
    'illustration rare': 'illustration_rare',
    'special illustration rare': 'special_illustration_rare',
    'hyper rare': 'hyper_rare', 'secret rare': 'secret_rare',
    'double rare': 'ultra_rare', 'shiny rare': 'secret_rare',
    'shiny holo rare': 'secret_rare', 'shiny ultra rare': 'secret_rare',
    'rainbow rare': 'hyper_rare', 'ace spec rare': 'ace_spec',
    'rare ace': 'ace_spec', 'prism rare': 'ultra_rare',
    'radiant rare': 'ultra_rare', 'rare break': 'ultra_rare',
    'amazing rare': 'ultra_rare', 'classic collection': 'ultra_rare',
    'mega hyper rare': 'mega_hyper_rare', 'mega attack rare': 'mega_attack_rare',
    'black white rare': 'rare', 'promo': 'rare', 'code card': 'common',
}

def get_era_code(era_name):
    era_slug_map = {
        'WotC Base':                ('WotC',  'WotC Era'),
        'WotC Legendary':           ('WotCL', 'WotC Legendary Era'),
        'WotC Neo':                 ('WotCN', 'WotC Neo Era'),
        'WotC Other':               ('WotCO', 'WotC Other'),
        'EX Era':                   ('EX',    'EX Era'),
        'Diamond & Pearl':          ('DP',    'Diamond & Pearl Era'),
        'HG&SS':                    ('HGSS',  'HeartGold SoulSilver Era'),
        'HeartGold SoulSilver':     ('HGSS',  'HeartGold SoulSilver Era'),
        'Black & White':            ('BW',    'Black & White Era'),
        'XY Era':                   ('XY',    'XY Era'),
        'Sun & Moon':               ('SM',    'Sun & Moon Era'),
        'Sword & Shield':           ('SWSH',  'Sword & Shield Era'),
        'Scarlet & Violet':         ('SV',    'Scarlet & Violet Era'),
        'Mega Evolution':           ('MEG',   'Mega Evolution Era'),
        'Special - Prize Pack':     ('PRIZE', 'Prize Pack Series'),
        'Special - Trick or Trade': ('TOT',   'Trick or Trade'),
        'Promo':                    ('PROMO', 'Promo'),
    }
    era_name = era_name.strip()
    return era_slug_map.get(era_name, ('OTHER', era_name))

def safe_decimal(val, default=None):
    try:
        v = str(val).strip()
        return Decimal(v) if v else default
    except InvalidOperation:
        return default

def safe_int(val, default=None):
    try:
        v = str(val).strip().split('/')[0].strip()
        return int(v) if v else default
    except (ValueError, TypeError):
        return default

def parse_legal(val):
    val = str(val).strip().lower()
    if val in ('legal', 'true', '1', 'yes'): return True
    if val in ('banned', 'false', '0', 'no'): return False
    return None

VARIANT_PRICE_MAP = {
    'Normal': 'price_normal', 'Holofoil': 'price_holo',
    'Reverse Holofoil': 'price_reverse_holo', '1st Edition': 'price_first_edition',
    'Poke Ball': 'price_pokeball', 'Master Ball': 'price_masterball',
    'Friend Ball': 'price_friendball', 'Love Ball': 'price_loveball',
    'Quick Ball': 'price_quickball', 'Dusk Ball': 'price_duskball',
}


def import_row(row, era_cache, set_cache, card_category, do_update, stats):
    """Import a single row. Called inside its own transaction.atomic() block."""
    from products.models import Era, CardSet, PokemonProduct

    era_name_raw = row.get('era', '').strip()
    era_code, era_full_name = get_era_code(era_name_raw)

    if era_code not in era_cache:
        era_obj, _ = Era.objects.get_or_create(
            code=era_code, defaults={'name': era_full_name}
        )
        era_cache[era_code] = era_obj

    set_code = row.get('set_code', '').strip()
    if set_code not in set_cache:
        set_obj, _ = CardSet.objects.get_or_create(
            code=set_code,
            defaults={'name': row.get('set_name', set_code), 'era': era_cache.get(era_code)}
        )
        set_cache[set_code] = set_obj

    rarity = RARITY_MAP.get(row.get('rarity', '').strip().lower(), 'common')
    variant = row.get('variant', '').strip()
    price = safe_decimal(row.get('pokebulk_zar'), Decimal('0')) or Decimal('0')
    product_id = safe_int(row.get('product_id'))

    image_url = (row.get('final_image_url') or row.get('tcgplayer_image_url') or '').strip()
    artist = (row.get('final_artist') or row.get('artist') or '').strip()[:200]
    pokedex_raw = (row.get('final_pokedex') or row.get('pokedex_numbers') or '').strip()

    defaults = {
        'name': row.get('name', '').strip(),
        'csv_sku': f"{set_code}-{row.get('number','').strip()}-{variant}",
        'tcgcsv_product_id': product_id,
        'card_set': set_cache.get(set_code),
        'category': card_category,
        'rarity': rarity,
        'artist': artist,
        'hp': safe_int(row.get('hp')),
        'image_url': image_url[:500] if image_url else '',
        'price': price,
        'legal_standard': parse_legal(row.get('legality_standard', '')),
        'legal_expanded': parse_legal(row.get('legality_expanded', '')),
        'legal_unlimited': True,
        'is_active': True,
        'stock': 0,
    }

    number_raw = row.get('number', '').strip()
    defaults['card_number'] = safe_int(number_raw)
    if pokedex_raw:
        defaults['pokedex_number'] = safe_int(pokedex_raw.split('|')[0])

    vp = VARIANT_PRICE_MAP.get(variant)
    if vp:
        defaults[vp] = price

    # Pre-set pb_id to guarantee uniqueness and bypass the auto-generator
    # tcgcsv_product_id is unique per variant; fall back to csv_sku
    defaults['pb_id'] = f"TCGCSV-{product_id}" if product_id else defaults['csv_sku']

    lookup = {'tcgcsv_product_id': product_id} if product_id else {'csv_sku': defaults['csv_sku']}
    existing = PokemonProduct.objects.filter(**lookup).first()

    if existing:
        if do_update:
            for k, v in defaults.items():
                if v is not None and v != '':
                    setattr(existing, k, v)
            existing.save(update_fields=list(defaults.keys()))
            stats['updated'] += 1
        else:
            stats['skipped'] += 1
    else:
        obj = PokemonProduct(**defaults)
        obj.save()
        stats['created'] += 1


class Command(BaseCommand):
    help = 'Import the final Bible CSV into the database'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--update', action='store_true')
        parser.add_argument('--limit', type=int, default=0)

    def handle(self, *args, **options):
        from products.models import Category

        csv_file = options['csv_file']
        dry_run = options['dry_run']
        do_update = options['update']
        limit = options['limit']

        if not os.path.exists(csv_file):
            raise CommandError(f'File not found: {csv_file}')

        self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Importing: {csv_file}')

        with open(csv_file, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        if limit:
            rows = rows[:limit]

        self.stdout.write(f'Total rows: {len(rows)}')

        card_category = None
        if not dry_run:
            card_category, _ = Category.objects.get_or_create(
                slug='pokemon-card', defaults={'name': 'Pokemon Card'}
            )

        stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        era_cache = {}
        set_cache = {}

        for i, row in enumerate(rows):
            if i % 1000 == 0:
                self.stdout.write(f'  [{i}/{len(rows)}]...')

            if dry_run:
                stats['created'] += 1
                continue

            try:
                with transaction.atomic():
                    import_row(row, era_cache, set_cache, card_category, do_update, stats)
            except Exception as e:
                stats['errors'] += 1
                self.stderr.write(f'  Error row {i} ({row.get("name","?")}): {e}')

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
