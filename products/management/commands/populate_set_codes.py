# PokeBulk SA - Populate CardSet tcgio_code and bulba_code
# v1.0.0
# Save to: C:\Users\texca\pokemart-api\products\management\commands\populate_set_codes.py
# Usage:
#     python manage.py populate_set_codes --dry-run
#     python manage.py populate_set_codes

import csv
import os
from django.core.management.base import BaseCommand
from products.models import CardSet

MAPPING_CSV = os.path.join(
    'C:\\', 'Users', 'texca', 'pokemart-api',
    'File dump from Downloads', 'master_set_mapping_v2.csv'
)


class Command(BaseCommand):
    help = 'Populate CardSet tcgio_code and bulba_code from master_set_mapping_v2.csv'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving',
        )
        parser.add_argument(
            '--csv',
            type=str,
            default=MAPPING_CSV,
            help='Path to master_set_mapping_v2.csv',
        )

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        csv_path = options['csv']

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('PokeBulk SA - Populate Set Codes v1.0.0')
        self.stdout.write('CSV     : ' + csv_path)
        self.stdout.write('Dry run : ' + str(dry_run))
        self.stdout.write('=' * 60 + '\n')

        if not os.path.exists(csv_path):
            self.stderr.write('ERROR: CSV not found: ' + csv_path)
            return

        # Read mapping CSV - db_code is master key
        mapping = {}
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                db_code = row.get('db_code', '').strip()
                tcgio   = row.get('tcgio_code', '').strip()
                bulba   = row.get('bulba_code', '').strip()
                if db_code and db_code not in mapping:
                    mapping[db_code] = {
                        'tcgio_code': tcgio,
                        'bulba_code': bulba,
                    }

        self.stdout.write('Loaded ' + str(len(mapping)) + ' set mappings\n')

        updated   = 0
        not_found = 0
        missing   = []
        to_update = []

        for cardset in CardSet.objects.all().order_by('code'):
            if cardset.code not in mapping:
                self.stdout.write('  WARNING: No mapping for: ' + cardset.code)
                missing.append(cardset.code)
                not_found += 1
                continue

            m = mapping[cardset.code]
            changed = False

            if cardset.tcgio_code != m['tcgio_code']:
                cardset.tcgio_code = m['tcgio_code']
                changed = True

            if cardset.bulba_code != m['bulba_code']:
                cardset.bulba_code = m['bulba_code']
                changed = True

            if changed:
                self.stdout.write(
                    '  ' + cardset.code.ljust(12) +
                    ' tcgio=' + m['tcgio_code'].ljust(15) +
                    ' bulba=' + m['bulba_code']
                )
                to_update.append(cardset)
                updated += 1

        if not dry_run and to_update:
            CardSet.objects.bulk_update(to_update, ['tcgio_code', 'bulba_code'])

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('DRY RUN - no changes saved' if dry_run else 'Done!')
        self.stdout.write('  Updated    : ' + str(updated))
        self.stdout.write('  Not in CSV : ' + str(not_found))
        if missing:
            self.stdout.write('  Missing    : ' + ', '.join(missing))
        self.stdout.write('=' * 60 + '\n')
