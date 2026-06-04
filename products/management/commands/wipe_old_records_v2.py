from django.core.management.base import BaseCommand
from products.models import PokemonProduct

class Command(BaseCommand):
    help = 'Delete truly old records - those with no tcgcsv_product_id and no csv_sku'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true')

    def handle(self, *args, **options):
        # True old records: no tcgcsv_product_id AND empty/null csv_sku
        old = PokemonProduct.objects.filter(
            tcgcsv_product_id__isnull=True,
            csv_sku=''
        )

        total = old.count()
        with_stock = old.filter(stock__gt=0).count()

        self.stdout.write(f"Old records (no tcgcsv_id, no csv_sku): {total}")
        self.stdout.write(f"With stock > 0: {with_stock}")

        if not options['confirm']:
            self.stdout.write("DRY RUN - pass --confirm to delete")
            return

        deleted, _ = old.delete()
        self.stdout.write(f"Deleted: {deleted}")
