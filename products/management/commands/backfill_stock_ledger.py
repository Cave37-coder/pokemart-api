"""One-off: seed the StockMovement ledger so existing cards don't show
"Loaded 0" on Stock Entry.

For every product with no ledger rows yet, writes one 'opening' row =
current stock + units already sold (Complete orders + manual invoices) +
units on open orders (already deducted from stock at checkout). That's the
best available estimate of what has been loaded before tracking started.
Safe to re-run: products that already have any ledger row are skipped.

    python manage.py backfill_stock_ledger            # dry run
    python manage.py backfill_stock_ledger --apply
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum

from orders.models import OrderItem, ManualInvoiceItem
from products.models import PokemonProduct, StockMovement


def _agg(qs):
    return {r['product_id']: r['t'] or 0 for r in qs.values('product_id').annotate(t=Sum('quantity'))}


class Command(BaseCommand):
    help = "Seed opening-balance rows in the stock ledger."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Write rows (default is a dry run).")

    def handle(self, *args, **opts):
        sold_o = _agg(OrderItem.objects.exclude(order__status='cancelled').filter(product__isnull=False))
        sold_m = _agg(ManualInvoiceItem.objects.exclude(invoice__status='cancelled').filter(product__isnull=False))
        has_rows = set(StockMovement.objects.values_list('product_id', flat=True).distinct())

        rows, total_units = [], 0
        for pid, stock in PokemonProduct.objects.values_list('id', 'stock').iterator():
            if pid in has_rows:
                continue
            opening = (stock or 0) + sold_o.get(pid, 0) + sold_m.get(pid, 0)
            if opening <= 0:
                continue
            rows.append(StockMovement(product_id=pid, delta=opening, stock_after=stock or 0, source='opening'))
            total_units += opening

        self.stdout.write(f"{len(rows)} products, {total_units} units of opening balance.")
        if not opts['apply']:
            self.stdout.write("Dry run -- re-run with --apply to write.")
            return
        StockMovement.objects.bulk_create(rows, batch_size=1000)
        self.stdout.write(self.style.SUCCESS("Done."))
