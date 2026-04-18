import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.management import call_command
from products.models import PokemonProduct, CardSet


class Command(BaseCommand):
    help = 'Delete and reimport a full set with enriched data'

    def add_arguments(self, parser):
        parser.add_argument('set_id', type=str, help='Pokemon TCG set ID e.g. base1')
        parser.add_argument('--stock', type=int, default=1, help='Initial stock per card')
        parser.add_argument('--delay', type=float, default=0.3, help='Delay between API calls')

    def handle(self, *args, **options):
        set_id = options['set_id']
        stock = options['stock']
        delay = options['delay']

        headers = {}
        if settings.POKEMONTCG_API_KEY:
            headers['X-Api-Key'] = settings.POKEMONTCG_API_KEY

        # Fetch set info
        self.stdout.write(f'Fetching set info for {set_id}...')
        set_response = requests.get(
            f'https://api.pokemontcg.io/v2/sets/{set_id}',
            headers=headers
        )

        if set_response.status_code != 200:
            self.stderr.write(f'Set not found: {set_id}')
            return

        set_data = set_response.json().get('data', {})
        set_name = set_data.get('name', set_id)
        set_code = set_data.get('ptcgoCode', set_id[:6].upper())
        total_cards = set_data.get('total', 0)

        self.stdout.write(self.style.SUCCESS(f'Found: {set_name} ({total_cards} cards)'))

        # Delete existing products for this set
        try:
            card_set = CardSet.objects.get(code=set_code)
            existing_count = PokemonProduct.objects.filter(card_set=card_set).count()
            if existing_count > 0:
                self.stdout.write(f'Deleting {existing_count} existing products for {set_name}...')
                PokemonProduct.objects.filter(card_set=card_set).delete()
                self.stdout.write(self.style.WARNING(f'Deleted {existing_count} products'))
        except CardSet.DoesNotExist:
            self.stdout.write('No existing products found — fresh import')

        # Fetch all cards
        self.stdout.write('Fetching card list...')
        cards_response = requests.get(
            f'https://api.pokemontcg.io/v2/cards?q=set.id:{set_id}&orderBy=number&pageSize=250',
            headers=headers
        )

        if cards_response.status_code != 200:
            self.stderr.write(f'Error fetching cards: {cards_response.status_code}')
            return

        cards = cards_response.json().get('data', [])
        self.stdout.write(f'Reimporting {len(cards)} cards with full enrichment...\n')

        imported = 0
        failed = 0

        for i, card in enumerate(cards, 1):
            card_id = card.get('id')
            card_name = card.get('name')

            self.stdout.write(f'[{i}/{len(cards)}] {card_name} ({card_id})...')

            try:
                call_command(
                    'import_card',
                    card_id,
                    stock=stock,
                    overwrite=True,
                    verbosity=0,
                )
                imported += 1
                self.stdout.write(self.style.SUCCESS('  ✓ Imported'))
            except SystemExit:
                imported += 1
                self.stdout.write(self.style.SUCCESS('  ✓ Imported'))
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Failed: {e}'))

            if delay and i < len(cards):
                time.sleep(delay)

        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'Enrichment complete for {set_name}'))
        self.stdout.write(f'  Imported: {imported}')
        self.stdout.write(f'  Failed:   {failed}')
        self.stdout.write(f'  Total:    {len(cards)}')