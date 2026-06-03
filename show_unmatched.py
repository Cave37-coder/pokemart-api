from django.core.management.base import BaseCommand
from products.models import PokemonProduct
from collections import defaultdict

class Command(BaseCommand):
    help = 'Show unmatched old-style records with stock'

    def handle(self, *args, **options):
        old = PokemonProduct.objects.exclude(
            name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
        ).filter(stock__gt=0).select_related('card_set')

        by_set = defaultdict(lambda: {'count': 0, 'stock': 0, 'name': '', 'samples': []})
        for p in old:
            c = p.card_set.code
            by_set[c]['count'] += 1
            by_set[c]['stock'] += p.stock
            by_set[c]['name'] = p.card_set.name
            if len(by_set[c]['samples']) < 2:
                by_set[c]['samples'].append(p.name)

        self.stdout.write(f"Total sets with unmatched stock: {len(by_set)}")
        for code in sorted(by_set.keys()):
            d = by_set[code]
            self.stdout.write(f"[{code}] {d['name']}: {d['count']} cards, stock={d['stock']}")
            for s in d['samples']:
                self.stdout.write(f"    {s}")
