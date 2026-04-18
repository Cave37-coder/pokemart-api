import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Import all cards from a Pokemon TCG set by set ID'

    def add_arguments(self, parser):
        parser.add_argument('set_id', type=str, help='Pokemon TCG set ID e.g. base1, swsh1, sv3pt5')
        parser.add_argument('--stock', type=int, default=1, help='Initial stock for each card')
        parser.add_argument('--delay', type=float, default=0.3, help='Delay between API calls in seconds')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of cards to import (0 = all)')

    def handle(self, *args, **options):
        set_id = options['set_id']
        stock = options['stock']
        delay = options['delay']
        limit = options['limit']

        self.stdout.write(f'Fetching set info for {set_id}...')

        headers = {}
        if settings.POKEMONTCG_API_KEY:
            headers['X-Api-Key'] = settings.POKEMONTCG_API_KEY

        # Fetch set info first
        set_response = requests.get(
            f'https://api.pokemontcg.io/v2/sets/{set_id}',
            headers=headers
        )

        if set_response.status_code != 200:
            self.stderr.write(f'Set not found: {set_id}')
            self.stderr.write('Find valid set IDs at: https://api.pokemontcg.io/v2/sets')
            return

        set_data = set_response.json().get('data', {})
        set_name = set_data.get('name', set_id)
        total_cards = set_data.get('total', 0)

        self.stdout.write(self.style.SUCCESS(
            f'Found set: {set_name} ({total_cards} cards)'
        ))

        if limit:
            self.stdout.write(f'Limiting to first {limit} cards')

        # Fetch all cards in the set
        self.stdout.write('Fetching card list...')
        cards_response = requests.get(
            f'https://api.pokemontcg.io/v2/cards?q=set.id:{set_id}&orderBy=number&pageSize=250',
            headers=headers
        )

        if cards_response.status_code != 200:
            self.stderr.write(f'Error fetching cards: {cards_response.status_code}')
            return

        cards = cards_response.json().get('data', [])

        if limit:
            cards = cards[:limit]

        self.stdout.write(f'Starting import of {len(cards)} cards...\n')

        imported = 0
        skipped = 0
        failed = 0

        for i, card in enumerate(cards, 1):
            card_id = card.get('id')
            card_name = card.get('name')
            card_number = card.get('number')

            self.stdout.write(f'[{i}/{len(cards)}] {card_name} ({card_id})...')

            try:
                call_command(
                    'import_card',
                    card_id,
                    stock=stock,
                    verbosity=0,
                )
                imported += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Imported'))
            except SystemExit:
                skipped += 1
                self.stdout.write(f'  → Skipped (already exists)')
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Failed: {e}'))

            if delay and i < len(cards):
                time.sleep(delay)

        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'Import complete for {set_name}'))
        self.stdout.write(f'  Imported: {imported}')
        self.stdout.write(f'  Skipped:  {skipped}')
        self.stdout.write(f'  Failed:   {failed}')
        self.stdout.write(f'  Total:    {len(cards)}')