"""
box_locations.py -- "which stock box do I pull this card from?" for the pull sheets (2026-10-28).

Michael: stock is used strictly OLDEST FIRST ("minused from oldest stock first, then moved to new buy-in
stock"). The pull sheet shows ONE place per card: the box holding the OLDEST copy still on the shelf; if
that copy is older than box tracking (stock that never came through a numbered buy-in) it says "Old Boxes".
That keeps new stock untouched while older copies remain, and means we never hunt in old stock for a
card that only exists as new stock.

There is no per-copy ledger, but oldest-first makes one unnecessary:
  * everything received for a card is known in order -- completed site buy-in lines (BuyOrder.box_number)
    and cards sorted out of bulk bundles (BulkSortEntry);
  * because the oldest are always sold first, the copies physically still here are simply the NEWEST ones:
    physical = stock now + units on orders/manual invoices not yet pulled (stock is deducted at checkout,
    the cards stay in their box until packed);
  * walking the receipts newest -> oldest until `physical` is covered gives the layout oldest -> newest
    ("Old Boxes" first when physical exceeds everything on record);
  * unpulled orders are served in the order they were placed, so each sheet starts where the earlier
    unpulled orders for that card end -- two open orders for the same card point at consecutive copies.
"""
from django.db.models import Q

from products.models import PokemonProduct

OLD = 'Old Boxes'
# Order statuses where the cards are still on the shelf (stock already deducted, not yet packed).
UNPULLED_ORDER = ('awaiting_payment', 'pending', 'pending_eft', 'printed', 'packed')
UNPULLED_MANUAL = ('created', 'pending_eft', 'printed', 'packed')


def box_locations(product_ids, current=None):
    """{product_id: 'Box 11' | 'Old Boxes'}.  current = ('order'|'manual', id) of the sheet being printed."""
    from .models import BuyOrderItem, BulkSortEntry, OrderItem, ManualInvoiceItem

    ids = {int(p) for p in product_ids if p}
    if not ids:
        return {}
    stock = dict(PokemonProduct.objects.filter(pk__in=ids).values_list('pk', 'stock'))

    # --- receipts per card: [(when, box, qty)] -----------------------------------------------
    receipts = {}
    lines = (BuyOrderItem.objects.select_related('buy_order')
             .filter(Q(stock_product_id__in=ids) | Q(stock_product__isnull=True, product_id__in=ids))
             .filter(buy_order__status='complete', buy_order__box_number__isnull=False))
    for it in lines:
        pid = it.stock_product_id or it.product_id
        if pid in ids:
            when = it.buy_order.completed_at or it.buy_order.created_at
            receipts.setdefault(pid, []).append((when, it.buy_order.box_number, it.quantity))
    sorts = (BulkSortEntry.objects.select_related('item__buy_order')
             .filter(stock_product_id__in=ids, item__buy_order__box_number__isnull=False))
    for se in sorts:
        receipts.setdefault(se.stock_product_id, []).append((se.created_at, se.item.buy_order.box_number, se.quantity))

    # --- unpulled demand per card: [(created_at, kind, id, qty)] -----------------------------
    demand = {}
    for oi in (OrderItem.objects.filter(product_id__in=ids, order__status__in=UNPULLED_ORDER)
               .select_related('order')):
        demand.setdefault(oi.product_id, []).append((oi.order.created_at, 'order', oi.order_id, oi.quantity))
    for mi in (ManualInvoiceItem.objects.filter(product_id__in=ids, invoice__status__in=UNPULLED_MANUAL)
               .select_related('invoice')):
        demand.setdefault(mi.product_id, []).append((mi.invoice.created_at, 'manual', mi.invoice_id, mi.quantity))

    out = {}
    for pid in ids:
        out[pid] = _label_for(receipts.get(pid, []), stock.get(pid, 0) or 0, demand.get(pid, []), current)
    return out


def _label_for(receipts, stock, demand, current):
    """Pure helper (unit-testable): receipts [(when, box, qty)], demand [(created, kind, id, qty)]."""
    queue = sorted(demand, key=lambda d: (d[0], d[1], d[2]))
    physical = stock + sum(d[3] for d in queue)
    offset = 0
    in_queue = False
    for d in queue:
        if current and (d[1], d[2]) == tuple(current):
            in_queue = True
            break
        offset += d[3]
    if current and not in_queue:
        # sheet for an order that is already packed: its cards aren't counted above, assume they came
        # off the front of the oldest copies.
        offset = 0
        physical += 1

    segs = []
    remaining = physical
    for when, box, qty in sorted(receipts, key=lambda r: (r[0] is not None, r[0]), reverse=True):
        if remaining <= 0:
            break
        take = min(qty, remaining)
        segs.append((f'Box {box}', take))
        remaining -= take
    layout = ([(OLD, remaining)] if remaining > 0 else []) + list(reversed(segs))
    if not layout:
        return OLD
    pos = offset
    label = layout[-1][0]
    for name, n in layout:
        if pos < n:
            label = name
            break
        pos -= n
    return label
