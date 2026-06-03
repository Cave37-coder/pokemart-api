from django.core.management.base import BaseCommand
from products.models import PokemonProduct

class Command(BaseCommand):
    help = 'Delete all old-style records (no variant suffix in name)'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true', help='Actually delete')

    def handle(self, *args, **options):
        old = PokemonProduct.objects.exclude(
            name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
        )

        total = old.count()
        with_stock = old.filter(stock__gt=0).count()

        self.stdout.write(f"Old-style records to delete: {total}")
        self.stdout.write(f"Of which have stock > 0: {with_stock}")

        if not options['confirm']:
            self.stdout.write("DRY RUN - pass --confirm to actually delete")
            return

        deleted, _ = old.delete()
        self.stdout.write(f"Deleted: {deleted}")
