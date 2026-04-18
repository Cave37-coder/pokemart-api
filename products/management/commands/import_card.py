import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import PokemonProduct, Category, PokemonType, Era, CardSet


RARITY_MAP = {
    'Common': 'common',
    'Uncommon': 'uncommon',
    'Rare': 'rare',
    'Rare Holo': 'holo_rare',
    'Rare Ultra': 'ultra_rare',
    'Rare Secret': 'secret_rare',
    'Rare Rainbow': 'legendary',
    'Rare Holo EX': 'ultra_rare',
    'Rare Holo GX': 'ultra_rare',
    'Rare Holo V': 'ultra_rare',
    'Rare Holo VMAX': 'ultra_rare',
    'Rare Holo VSTAR': 'ultra_rare',
    'Illustration Rare': 'ultra_rare',
    'Special Illustration Rare': 'secret_rare',
    'Hyper Rare': 'secret_rare',
    'Amazing Rare': 'ultra_rare',
    'Promo': 'rare',
}

VARIANT_MAP = {
    'common': 'S',
    'uncommon': 'S',
    'rare': 'S',
    'holo_rare': 'H',
    'ultra_rare': 'FA',
    'secret_rare': 'SR',
    'legendary': 'RA',
}

ERA_MAP = {
    'base1': ('B1', 'WotC Base Era'),
    'base2': ('B1', 'WotC Base Era'),
    'base3': ('B1', 'WotC Base Era'),
    'base4': ('B1', 'WotC Base Era'),
    'base5': ('B1', 'WotC Base Era'),
    'base6': ('B1', 'WotC Base Era'),
    'gym1': ('B1', 'WotC Base Era'),
    'gym2': ('B1', 'WotC Base Era'),
    'neo1': ('B1', 'WotC Base Era'),
    'neo2': ('B1', 'WotC Base Era'),
    'neo3': ('B1', 'WotC Base Era'),
    'neo4': ('B1', 'WotC Base Era'),
    'ecard1': ('B1', 'WotC Base Era'),
    'ecard2': ('B1', 'WotC Base Era'),
    'ecard3': ('B1', 'WotC Base Era'),
}


def get_era_for_set(set_id, series):
    if set_id in ERA_MAP:
        return ERA_MAP[set_id]
    series_lower = series.lower() if series else ''
    if 'ex' in series_lower:
        return ('B2', 'EX Era')
    elif 'diamond' in series_lower or 'pearl' in series_lower or 'platinum' in series_lower:
        return ('B3', 'Diamond & Pearl Era')
    elif 'black' in series_lower or 'white' in series_lower:
        return ('B4', 'Black & White Era')
    elif 'xy' in series_lower:
        return ('B5', 'XY Era')
    elif 'sun' in series_lower or 'moon' in series_lower:
        return ('B6', 'Sun & Moon Era')
    elif 'sword' in series_lower or 'shield' in series_lower:
        return ('B7', 'Sword & Shield Era')
    elif 'scarlet' in series_lower or 'violet' in series_lower:
        return ('B8', 'Scarlet & Violet Era')
    return ('PR', 'Promo')


class Command(BaseCommand):
    help = 'Import a Pokemon card by its TCG API ID'

    def add_arguments(self, parser):
        parser.add_argument('card_id', type=str, help='Pokemon TCG API card ID e.g. base1-4')
        parser.add_argument('--price', type=float, default=0.0, help='Manual price override')
        parser.add_argument('--stock', type=int, default=1, help='Initial stock quantity')

    def handle(self, *args, **options):
        card_id = options['card_id']
        manual_price = options['price']
        stock = options['stock']

        self.stdout.write(f'Fetching card {card_id} from Pokemon TCG API...')

        headers = {}
        if settings.POKEMONTCG_API_KEY:
            headers['X-Api-Key'] = settings.POKEMONTCG_API_KEY

        response = requests.get(
            f'https://api.pokemontcg.io/v2/cards/{card_id}',
            headers=headers
        )

        if response.status_code != 200:
            self.stderr.write(f'Error fetching card: {response.status_code}')
            return

        data = response.json().get('data', {})

        # Extract card info
        name = data.get('name', '')
        rarity_raw = data.get('rarity', 'Common')
        rarity = RARITY_MAP.get(rarity_raw, 'common')
        tcgplayer_id = str(data.get('tcgplayer', {}).get('url', '').split('/')[-1] or '')
        image_url = data.get('images', {}).get('large', '')
        number = data.get('number', '0')
        national_pokedex = data.get('nationalPokedexNumbers', [None])[0]

        # Extract set info
        set_data = data.get('set', {})
        set_id = set_data.get('id', '')
        set_name = set_data.get('name', '')
        set_code = set_data.get('ptcgoCode', set_id[:6].upper())
        series = set_data.get('series', '')
        total = set_data.get('total', 999)

        # Get or create Era
        era_code, era_name = get_era_for_set(set_id, series)
        era, _ = Era.objects.get_or_create(code=era_code, defaults={'name': era_name})

        # Get or create CardSet
        card_set, _ = CardSet.objects.get_or_create(
            code=set_code,
            defaults={'name': set_name, 'era': era}
        )

        # Get or create Category
        category, _ = Category.objects.get_or_create(
            slug='cards',
            defaults={'name': 'Cards'}
        )

        # Get or create Pokemon Types
        types_raw = data.get('types', [])
        pokemon_types = []
        for t in types_raw:
            pt, _ = PokemonType.objects.get_or_create(name=t)
            pokemon_types.append(pt)

        # Parse card number
        try:
            card_number = int(''.join(filter(str.isdigit, number))) or 1
        except Exception:
            card_number = 1

        # Get TCGplayer price
        price = manual_price
        if price == 0.0:
            tcg_prices = data.get('tcgplayer', {}).get('prices', {})
            for price_type in ['holofoil', 'reverseHolofoil', 'normal', '1stEditionHolofoil']:
                if price_type in tcg_prices:
                    market = tcg_prices[price_type].get('market')
                    if market:
                        price = round(market * 18.5, 2)  # Convert USD to ZAR
                        self.stdout.write(f'Price from TCGplayer: ${market} USD = R{price} ZAR')
                        break

        # Check if product already exists
        existing = PokemonProduct.objects.filter(
            card_set=card_set,
            card_number=card_number,
            rarity=rarity,
        ).first()

        if existing:
            self.stdout.write(self.style.WARNING(f'Card already exists: {existing.pb_id}'))
            return

        # Create product
        product = PokemonProduct(
            name=name,
            category=category,
            card_set=card_set,
            rarity=rarity,
            pokedex_number=national_pokedex,
            card_number=card_number,
            price=price if price > 0 else 0,
            stock=stock,
            tcgplayer_id=tcgplayer_id,
            description=f'{rarity_raw} card from {set_name}',
        )
        product.save()

        # Add types
        if pokemon_types:
            product.pokemon_types.set(pokemon_types)

        self.stdout.write(self.style.SUCCESS(
            f'Successfully imported: {product.pb_id} — {product.name} @ R{product.price}'
        ))
        self.stdout.write(f'SKU: {product.sku}')
        self.stdout.write(f'TCGplayer ID: {product.tcgplayer_id}')
        self.stdout.write(f'Image URL: {image_url}')