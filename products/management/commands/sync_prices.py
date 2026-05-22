import math, os, sys
import requests
import django
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = 'Fetch latest prices from TCGCSV and update all products'

    def handle(self, *args, **kwargs):
        from products.models import PokemonProduct

        MARKUP = Decimal('1.10')
        RATE = Decimal('16.49')

        def to_zar(usd):
            return Decimal(math.ceil(float(Decimal(str(usd)) * RATE * MARKUP) * 2)) / 2

        self.stdout.write('Fetching prices from TCGCSV...')
        url = 'https://tcgcsv.com/tcgplayer/prices'
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        raw = r.json()

        price_map = {}
        for key, usd in raw.items():
            pid_str, subtype = key.split('|', 1)
            pid = int(pid_str)
            price_map.setdefault(pid, {})[subtype] = float(usd)

        self.stdout.write(f'  {len(price_map):,} products with prices')

        def get_price(pid, variant):
            subtypes = price_map.get(pid, {})
            if not subtypes:
                return None
            if variant in ('N', '1E'):
                return (subtypes.get('Normal') or subtypes.get('Unlimited Normal') or
                        subtypes.get('1st Edition Normal') or subtypes.get('Holofoil'))
            elif variant in ('H', 'SHN'):
                return (subtypes.get('Holofoil') or subtypes.get('1st Edition Holofoil') or
                        subtypes.get('Unlimited Holofoil'))
            elif variant == 'RH':
                return (subtypes.get('Reverse Holofoil') or subtypes.get('Holofoil'))
            else:
                return (subtypes.get('Normal') or subtypes.get('Holofoil') or
                        (list(subtypes.values())[0] if subtypes else None))

        self.stdout.write('Updating prices...')
        updated = skipped = no_price = 0
        to_update = []

        for p in PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True).iterator(chunk_size=2000):
            pid = p.tcgcsv_product_id
            var = p.variant_override or 'N'
            usd = get_price(pid, var)
            if usd is None:
                no_price += 1
                continue
            new_price = to_zar(usd)
            if p.price == new_price:
                skipped += 1
                continue
            p.price = new_price
            to_update.append(p)
            updated += 1
            if len(to_update) >= 2000:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(to_update, ['price'])
                self.stdout.write(f'  ...wrote {updated:,}')
                to_update = []

        if to_update:
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(to_update, ['price'])

        self.stdout.write(f'Done. Updated={updated:,}  Skipped={skipped:,}  No price={no_price:,}')
