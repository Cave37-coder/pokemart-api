from django.core.management.base import BaseCommand
from products.models import PokemonProduct
from django.db import transaction

class Command(BaseCommand):
    help = 'Transfer stock from old Holo records to new Holofoil records'

    def handle(self, *args, **options):
        # Find all old (Holo) records with stock
        holo_records = PokemonProduct.objects.filter(
            name__endswith=' (Holo)',
            stock__gt=0
        ).select_related('card_set')

        self.stdout.write(f"Old (Holo) records with stock: {holo_records.count()}")

        transferred = 0
        not_found = []

        for old in holo_records:
            base = old.name[:-7]  # strip ' (Holo)'
            new = PokemonProduct.objects.filter(
                card_set=old.card_set,
                name=base + ' (Holofoil)'
            ).first()

            if new:
                with transaction.atomic():
                    new.stock += old.stock
                    new.save(update_fields=['stock'])
                    old.stock = 0
                    old.save(update_fields=['stock'])
                    transferred += 1
                    self.stdout.write(f"  OK [{old.card_set.code}] '{old.name}' ({old.stock+new.stock-new.stock}) -> '{new.name}'")
            else:
                not_found.append(f"[{old.card_set.code}] '{old.name}' stock={old.stock}")

        self.stdout.write(f"\nTransferred: {transferred}")
        self.stdout.write(f"Not found: {len(not_found)}")
        for nf in not_found:
            self.stdout.write(f"  {nf}")
