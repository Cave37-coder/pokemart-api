"""
link_accessories_to_pile -- 2026-11-08

One-off (safe to re-run): gives every accessory its product row so it can
be added to My Pile and bought (see accessories/cart_link.py).

    python manage.py link_accessories_to_pile --dry-run
    python manage.py link_accessories_to_pile
"""
from django.core.management.base import BaseCommand

from accessories.cart_link import push_to_product
from accessories.models import Accessory


class Command(BaseCommand):
    help = "Create/refresh the Pile product row for every accessory."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        qs = Accessory.objects.all()
        new = qs.filter(cart_product__isnull=True)
        self.stdout.write(f"{qs.count()} accessories, {new.count()} not linked yet "
                          f"({qs.filter(is_active=True, stock__gt=0).count()} on sale now)")
        if o["dry_run"]:
            for a in new.filter(stock__gt=0)[:20]:
                self.stdout.write(f"  WOULD LINK: {a.sku} {a.name} R{a.price} stock {a.stock}")
            self.stdout.write("Dry run -- nothing written.")
            return
        linked = refreshed = 0
        for a in qs.iterator():
            was_new = a.cart_product_id is None
            # First link copies Accessory.stock onto the product; later runs only
            # refresh name/price/image (never overwrite live stock).
            push_to_product(a)
            linked += was_new
            refreshed += (not was_new)
        self.stdout.write(self.style.SUCCESS(f"Linked {linked} new, refreshed {refreshed}."))
