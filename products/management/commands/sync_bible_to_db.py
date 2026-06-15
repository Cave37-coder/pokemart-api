# PokeBulk SA - Sync Bible v6 to Django DB
# v1.0.2
# Batches saves in chunks of 500 to avoid Railway DB connection timeouts
# Reconnects on connection errors
#
# Save to: C:\Users\texca\pokemart-api\products\management\commands\sync_bible_to_db.py
#
# Usage:
#   python manage.py sync_bible_to_db --dry-run
#   python manage.py sync_bible_to_db
#   python manage.py sync_bible_to_db --set-code BS

import csv
import os
import re
from django.core.management.base import BaseCommand
from django.db import connection
from products.models import PokemonProduct

BIBLE_PATH  = os.path.join('C:\\', 'Users', 'texca', 'pokemart-api', 'pokebulk_bible_v6.csv')
BATCH_SIZE  = 200

MAX = {
    'artist':           200,
    'supertype':        50,
    'card_subtypes':    200,
    'weakness_type':    50,
    'weakness_value':   10,
    'resistance_type':  50,
    'resistance_value': 10,
    'attack_1_name':    200,
    'attack_1_damage':  20,
    'attack_2_name':    200,
    'attack_2_damage':  20,
    'number':           20,
}


def trunc(val, field):
    if not val:
        return val
    limit = MAX.get(field)
    if limit and len(str(val)) > limit:
        return str(val)[:limit]
    return val


def parse_attack(raw):
    if not raw:
        return '', '', ''
    raw = re.sub(r'<[^>]+>', ' ', raw).strip()
    raw = re.sub(r'\s+', ' ', raw)
    lines = raw.split('\n')
    first = lines[0].strip()
    damage = ''
    dmg_match = re.search(r'\(([0-9+\-×x]+)\)\s*$', first)
    if dmg_match:
        damage = dmg_match.group(1)
        first = first[:dmg_match.start()].strip()
    cost_match = re.match(r'^\[[^\]]+\]\s*', first)
    if cost_match:
        first = first[cost_match.end():].strip()
    text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''
    return first, damage, text


def parse_weakness(raw):
    if not raw:
        return '', ''
    raw = raw.strip()
    match = re.match(r'^([A-Za-z]+)\s*([×x+\-]?\d+)?', raw)
    if match:
        return match.group(1), match.group(2) or ''
    return raw[:50], ''


def safe_int(val):
    if not val:
        return None
    try:
        return int(str(val).strip().split('.')[0])
    except (ValueError, TypeError):
        return None


def clean_html(val):
    if not val:
        return ''
    val = re.sub(r'<[^>]+>', ' ', str(val)).strip()
    return re.sub(r'\s+', ' ', val)


def ensure_connection():
    try:
        connection.ensure_connection()
    except Exception:
        connection.close()
        connection.ensure_connection()


class Command(BaseCommand):
    help = 'Sync bible v6 card data into Django DB v1.0.2'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--set-code', type=str, default=None)
        parser.add_argument('--bible', type=str, default=BIBLE_PATH)
        parser.add_argument('--overwrite', action='store_true')
        parser.add_argument('--batch-size', type=int, default=BATCH_SIZE)

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        set_filter = options['set_code']
        bible_path = options['bible']
        overwrite  = options['overwrite']
        batch_size = options['batch_size']

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('PokeBulk SA - Sync Bible to DB v1.0.2')
        self.stdout.write('Bible      : ' + bible_path)
        self.stdout.write('Dry run    : ' + str(dry_run))
        self.stdout.write('Overwrite  : ' + str(overwrite))
        self.stdout.write('Batch size : ' + str(batch_size))
        self.stdout.write('=' * 60 + '\n')

        # Load bible
        self.stdout.write('Loading bible...')
        bible_by_pid = {}
        with open(bible_path, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                pid = str(row.get('product_id', '')).strip()
                if pid and pid not in bible_by_pid:
                    bible_by_pid[pid] = row
        self.stdout.write('  ' + str(len(bible_by_pid)) + ' unique products\n')

        # Load DB products
        self.stdout.write('Loading DB products...')
        db_qs = PokemonProduct.objects.select_related('card_set')
        if set_filter:
            db_qs = db_qs.filter(card_set__code=set_filter)
        db_products = list(db_qs)
        self.stdout.write('  ' + str(len(db_products)) + ' products\n')

        updated = unchanged = not_found = errors = saved = 0
        to_update = []

        def flush_batch(batch):
            nonlocal saved, errors
            ensure_connection()
            for product, fields in batch:
                try:
                    product.save(update_fields=list(set(fields + ['updated_at'])))
                    saved += 1
                except Exception as e:
                    self.stdout.write('  ERROR ' + str(product.tcgcsv_product_id) + ': ' + str(e))
                    errors += 1
                    ensure_connection()
            self.stdout.write('  Batch saved: ' + str(saved) + ' total')

        for product in db_products:
            pid = str(product.tcgcsv_product_id) if product.tcgcsv_product_id else ''
            if not pid:
                not_found += 1
                continue

            bible_row = bible_by_pid.get(pid)
            if not bible_row:
                not_found += 1
                continue

            changed = False
            fields_to_save = []

            def update_str(field, val):
                nonlocal changed
                if not val:
                    return
                val = trunc(str(val).strip(), field)
                current = getattr(product, field, '') or ''
                if overwrite or not current:
                    if current != val:
                        setattr(product, field, val)
                        fields_to_save.append(field)
                        changed = True

            def update_int(field, val):
                nonlocal changed
                v = safe_int(val)
                if v is None:
                    return
                current = getattr(product, field, None)
                if overwrite or current is None:
                    if current != v:
                        setattr(product, field, v)
                        fields_to_save.append(field)
                        changed = True

            def update_text(field, val):
                nonlocal changed
                val = clean_html(val)
                if not val:
                    return
                current = getattr(product, field, '') or ''
                if overwrite or not current:
                    if current != val:
                        setattr(product, field, val)
                        fields_to_save.append(field)
                        changed = True

            update_int('hp', bible_row.get('hp', ''))
            update_int('retreat_cost', bible_row.get('retreat_cost', ''))
            update_str('card_subtypes', bible_row.get('card_type', ''))
            update_str('supertype', bible_row.get('stage', ''))

            wtype, wval = parse_weakness(bible_row.get('weakness', ''))
            update_str('weakness_type', wtype)
            update_str('weakness_value', wval)

            rtype, rval = parse_weakness(bible_row.get('resistance', ''))
            update_str('resistance_type', rtype)
            update_str('resistance_value', rval)

            a1_raw = bible_row.get('attack_1', '')
            if a1_raw:
                a1_name, a1_dmg, a1_text = parse_attack(a1_raw)
                update_str('attack_1_name', a1_name)
                update_str('attack_1_damage', a1_dmg)
                update_text('attack_1_text', a1_text)

            a2_raw = bible_row.get('attack_2', '')
            if a2_raw:
                a2_name, a2_dmg, a2_text = parse_attack(a2_raw)
                update_str('attack_2_name', a2_name)
                update_str('attack_2_damage', a2_dmg)
                update_text('attack_2_text', a2_text)

            update_text('description', bible_row.get('card_text', ''))
            artist = bible_row.get('final_artist', '') or bible_row.get('artist', '')
            update_str('artist', artist)
            update_str('number', bible_row.get('number', ''))
            update_text('flavour_text', bible_row.get('ext_FlavorText', ''))

            if changed:
                to_update.append((product, fields_to_save))
                updated += 1
                if not dry_run and len(to_update) >= batch_size:
                    flush_batch(to_update)
                    to_update = []
            else:
                unchanged += 1

        # Flush remaining
        if not dry_run and to_update:
            flush_batch(to_update)

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('DRY RUN - no changes saved' if dry_run else 'Done!')
        self.stdout.write('  Updated   : ' + str(updated))
        self.stdout.write('  Unchanged : ' + str(unchanged))
        self.stdout.write('  Not found : ' + str(not_found))
        if not dry_run:
            self.stdout.write('  Saved     : ' + str(saved))
            self.stdout.write('  Errors    : ' + str(errors))
        self.stdout.write('=' * 60 + '\n')
