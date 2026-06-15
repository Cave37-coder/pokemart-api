# PokeBulk SA - Update Product Image URLs to R2
# v1.0.2
# Handles all special set card number prefixes correctly
#
# Save to: C:\Users\texca\pokemart-api\products\management\commands\update_r2_images.py

from django.core.management.base import BaseCommand
from products.models import PokemonProduct

R2_BASE = "https://pub-77a8c30ac1fc4f4fbe1f2a7a0f15f174.r2.dev"

# Sets with special card number prefixes in filenames
# format: set_code -> (prefix, padding, lowercase_folder)
# prefix: string to prepend to number
# padding: zero-pad width (0 = no padding)
# lowercase: whether folder/file uses lowercase
SPECIAL_SETS = {
    'CRZGG':   ('GG',   2, False),
    'BRSTG':   ('TG',   2, False),
    'ASRTG':   ('TG',   2, False),
    'LORTG':   ('TG',   2, False),
    'SITTG':   ('TG',   2, False),
    'HIFSV':   ('SV',   0, False),  # no padding e.g. SV1, SV10
    'SHFSV':   ('SV',   3, False),  # 3-digit e.g. SV001
    'PR-SWSH': ('SWSH', 3, False),  # e.g. SWSH001
    'PR-BLW':  ('BW',   2, False),  # e.g. BW01
    'PR-XY':   ('XY',   2, False),  # e.g. XY01
    'SVP':     ('',     3, True),   # lowercase, plain e.g. svp_001
    'SMP':     ('SM',   2, True),   # lowercase, SM prefix e.g. smp_SM02
}


def get_card_filename(set_code, number_raw, card_number):
    """
    Build the correct filename for a card based on set-specific rules.
    Returns just the filename part e.g. BS_001.jpg
    """
    special = SPECIAL_SETS.get(set_code)

    if special:
        prefix, padding, lowercase = special
        folder = set_code.lower() if lowercase else set_code

        # Use number field (raw) if available, strip the /total part
        num_str = str(number_raw).split('/')[0].strip() if number_raw else ''

        if not num_str and card_number is not None:
            num_str = str(card_number)

        if not num_str:
            return None

        # Remove any existing prefix from number
        # e.g. "GG01" -> "01", "TG15" -> "15", "SV001" -> "001"
        for p in ['GG', 'TG', 'SV', 'SWSH', 'BW', 'XY', 'SM']:
            if num_str.upper().startswith(p):
                num_str = num_str[len(p):]
                break

        # Apply padding
        if padding > 0 and num_str.isdigit():
            num_str = num_str.zfill(padding)

        filename = folder + '_' + prefix + num_str + '.jpg'
        return folder, filename

    else:
        # Standard sets — uppercase, plain 3-digit number
        folder = set_code.upper()

        num_str = ''
        if number_raw:
            num_str = str(number_raw).split('/')[0].strip()
            # Handle special characters
            num_str = num_str.replace('?', 'QM').replace('!', 'EM')

        if not num_str and card_number is not None:
            num_str = str(card_number)

        if not num_str:
            return None

        if num_str.isdigit():
            num_str = num_str.zfill(3)

        filename = folder + '_' + num_str + '.jpg'
        return folder, filename


class Command(BaseCommand):
    help = 'Update all product image_url to point to R2 v1.0.2'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run',   action='store_true')
        parser.add_argument('--set-code',  type=str, default=None)
        parser.add_argument('--overwrite', action='store_true')

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        set_filter = options['set_code']
        overwrite  = options['overwrite']

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('PokeBulk SA - Update R2 Image URLs v1.0.2')
        self.stdout.write('R2 Base   : ' + R2_BASE)
        self.stdout.write('Dry run   : ' + str(dry_run))
        self.stdout.write('Set filter: ' + (set_filter or 'ALL'))
        self.stdout.write('Overwrite : ' + str(overwrite))
        self.stdout.write('=' * 60 + '\n')

        qs = PokemonProduct.objects.select_related('card_set').all()
        if set_filter:
            qs = qs.filter(card_set__code__iexact=set_filter)

        total = qs.count()
        self.stdout.write('Total products: ' + str(total) + '\n')

        to_update         = []
        skipped_no_set    = 0
        skipped_no_number = 0
        skipped_correct   = 0
        updated           = 0

        for product in qs.iterator(chunk_size=500):
            if not product.card_set:
                skipped_no_set += 1
                continue

            set_code = product.card_set.code
            number_raw  = product.number or ''
            card_number = product.card_number

            result = get_card_filename(set_code, number_raw, card_number)
            if not result:
                skipped_no_number += 1
                continue

            folder, filename = result
            new_url = R2_BASE + '/cards/' + folder + '/' + filename

            if not overwrite and product.image_url == new_url:
                skipped_correct += 1
                continue

            product.image_url       = new_url
            product.image_small_url = new_url
            to_update.append(product)
            updated += 1

            if len(to_update) >= 500:
                self.stdout.write('  Saved ' + str(updated) + ' so far...')
                if not dry_run:
                    PokemonProduct.objects.bulk_update(
                        to_update, ['image_url', 'image_small_url']
                    )
                to_update = []

        if to_update and not dry_run:
            PokemonProduct.objects.bulk_update(
                to_update, ['image_url', 'image_small_url']
            )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('DRY RUN - no changes saved' if dry_run else 'Done!')
        self.stdout.write('  Updated            : ' + str(updated))
        self.stdout.write('  Skipped (no set)   : ' + str(skipped_no_set))
        self.stdout.write('  Skipped (no number): ' + str(skipped_no_number))
        self.stdout.write('  Skipped (correct)  : ' + str(skipped_correct))
        self.stdout.write('=' * 60 + '\n')

        if dry_run:
            self.stdout.write('Sample URLs:')
            count = 0
            for p in qs.iterator(chunk_size=100):
                if not p.card_set or count >= 10:
                    break
                result = get_card_filename(p.card_set.code, p.number or '', p.card_number)
                if result:
                    folder, filename = result
                    url = R2_BASE + '/cards/' + folder + '/' + filename
                    self.stdout.write('  ' + p.card_set.code + ' | ' + p.name + ' -> ' + filename)
                    count += 1
