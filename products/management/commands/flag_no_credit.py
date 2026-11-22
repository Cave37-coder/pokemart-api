"""
flag_no_credit -- put cards on / take them off the "No store credit" list (Michael, 2026-11-22).

A flagged card can't be paid for with a customer's store credit (checkout applies credit to the other cards only).
Normally you tick "No store credit" on a Buy-in line; this command does it after the fact, e.g. for a completed invoice.

    python manage.py flag_no_credit BUY-00023                 # DRY RUN: lists the cards that would be flagged
    python manage.py flag_no_credit BUY-00023 --apply
    python manage.py flag_no_credit BUY-00023 --apply --min-price 500   # only cards priced R500+ on the site
    python manage.py flag_no_credit BUY-00023 --apply --off             # take them off the list again
    python manage.py flag_no_credit --list                               # show everything currently flagged
The flag goes on the row that actually received the stock (the played copy for MP/LP/HP lines).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from orders.models import BuyOrder
from products.models import PokemonProduct


class Command(BaseCommand):
    help = "Flag/unflag cards as 'No store credit' from a buying invoice (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("buy_numbers", nargs="*", help="e.g. BUY-00023")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--off", action="store_true", help="remove the flag instead of setting it")
        parser.add_argument("--min-price", type=Decimal, default=None, help="only cards whose site price is at least this (R)")
        parser.add_argument("--list", action="store_true", help="list every card currently flagged")

    def handle(self, *args, **o):
        if o["list"]:
            rows = PokemonProduct.objects.filter(no_store_credit=True).select_related("card_set").order_by("-price")
            self.stdout.write(f"{rows.count()} card(s) currently flagged 'No store credit':")
            for p in rows:
                self.stdout.write(f"  {p.card_set.code if p.card_set else '-':8} {p.name[:44]:44} {p.condition} {p.variant_override or 'N':3} R{p.price}  stock {p.stock}")
            return
        if not o["buy_numbers"]:
            self.stdout.write(self.style.ERROR("Give a buying invoice number, e.g. BUY-00023 (or use --list)."))
            return
        want = not o["off"]
        total = 0
        for num in o["buy_numbers"]:
            buy = BuyOrder.objects.filter(buy_number__iexact=num).first()
            if not buy:
                self.stdout.write(self.style.ERROR(f"{num}: not found"))
                continue
            seen, rows = set(), []
            for it in buy.items.select_related("product", "stock_product", "product__card_set").all():
                p = it.stock_product or it.product
                if not p or p.pk in seen:
                    continue
                seen.add(p.pk)
                rows.append(p)
            self.stdout.write(f"\n{buy.buy_number}: {len(rows)} card(s) -> {'FLAG' if want else 'UNFLAG'} ({'APPLY' if o['apply'] else 'DRY RUN'})")
            for i, p in enumerate(rows, 1):
                skip = o["min_price"] is not None and (p.price or 0) < o["min_price"]
                note = "  (skipped: under --min-price)" if skip else ("  (already)" if p.no_store_credit == want else "")
                self.stdout.write(f"  [{i}/{len(rows)}] {p.name[:42]:42} {p.condition} {p.variant_override or 'N':3} R{p.price}{note}")
                if skip or not o["apply"]:
                    continue
                if p.no_store_credit != want:
                    PokemonProduct.objects.filter(pk=p.pk).update(no_store_credit=want)
                total += 1
        if o["apply"]:
            self.stdout.write(self.style.SUCCESS(f"\nDone: {total} card(s) {'flagged' if want else 'unflagged'}."))
        else:
            self.stdout.write(self.style.WARNING("\nDry run -- nothing written. Add --apply to do it."))
