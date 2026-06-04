from django.core.management.base import BaseCommand
from products.models import PokemonProduct

class Command(BaseCommand):
    help = 'Delete wrong-style records that have variant appended to name e.g. "Charizard (Normal)"'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true')

    def handle(self, *args, **options):
        # Wrong records: name ends with (Normal), (Holofoil), (Reverse Holo) etc
        # These were created by import_bible_v2.py which incorrectly appended variant to name
        wrong = PokemonProduct.objects.filter(
            name__regex=r'\((Normal|Holofoil|Reverse Holo|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
        )

        total = wrong.count()
        with_stock = wrong.filter(stock__gt=0).count()

        self.stdout.write(f"Wrong-style records to delete: {total}")
        self.stdout.write(f"Of which have stock > 0: {with_stock}")

        if with_stock > 0:
            self.stdout.write("WARNING: Some have stock — these should be 0 since correct records now exist")

        if not options['confirm']:
            self.stdout.write("DRY RUN - pass --confirm to actually delete")
            return

        deleted, _ = wrong.delete()
        self.stdout.write(f"Deleted: {deleted}")
