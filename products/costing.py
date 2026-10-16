"""Weighted-average cost tracking per product (2026-10-16).

Michael: "we need to trace that" -- what we paid for stock, and what each sale
cost us. PokemonProduct carries two counters: `cost_units` (units on hand whose
purchase cost we know) and `cost_total` (their combined cost). avg_cost =
cost_total / cost_units.

* A completed buying invoice calls add_cost() with the EFFECTIVE unit cost
  (line price scaled to what was actually paid for the whole invoice).
* A sale calls consume_cost(): it takes units at the current average, shrinks
  the counters, and returns the unit cost to snapshot on the sale line.
* Deleting/reducing a sale calls restore_cost() to put that cost back.

Stock that predates this feature has no known cost, so it simply isn't counted
in cost_units; a sale of mixed known/unknown stock is costed at the average of
the known units (approximate). All helpers use SQL updates so they never
overwrite other fields.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F

FOUR = Decimal('0.0001')


def add_cost(product_id, qty, unit_cost):
    """Record `qty` units bought at `unit_cost` each. Call AFTER the stock has
    been increased. Costed units can never exceed the stock that existed before
    this purchase (stock zeroed/changed by hand leaves stale counters, which are
    scaled back here so they cannot skew the average)."""
    from .models import PokemonProduct
    if not product_id or not qty or unit_cost is None:
        return
    with transaction.atomic():
        row = PokemonProduct.objects.select_for_update().filter(pk=product_id).values(
            'stock', 'cost_units', 'cost_total').first()
        if row is None:
            return
        known, total = row['cost_units'], Decimal(row['cost_total'])
        allowed = max(row['stock'] - qty, 0)
        if known > allowed:
            total = (total * allowed / known) if known else Decimal('0')
            known = allowed
        PokemonProduct.objects.filter(pk=product_id).update(
            cost_units=known + qty,
            cost_total=(total + Decimal(unit_cost) * qty).quantize(Decimal('0.01')),
        )


def adjust_cost_total(product_id, delta):
    """Shift the cost total without changing unit counts (invoice re-priced)."""
    from .models import PokemonProduct
    if product_id and delta:
        PokemonProduct.objects.filter(pk=product_id).update(cost_total=F('cost_total') + Decimal(delta))


def consume_cost(product_id, qty):
    """Take `qty` units out at the current average. Returns the unit cost used
    (Decimal) or None when no costed units exist for this product."""
    from .models import PokemonProduct
    if not product_id or not qty:
        return None
    with transaction.atomic():
        p = PokemonProduct.objects.select_for_update().filter(pk=product_id).values('cost_units', 'cost_total').first()
        if not p or not p['cost_units'] or p['cost_units'] <= 0:
            return None
        avg = (p['cost_total'] / p['cost_units']).quantize(FOUR)
        take = min(qty, p['cost_units'])
        new_total = max(p['cost_total'] - avg * take, Decimal('0'))
        PokemonProduct.objects.filter(pk=product_id).update(
            cost_units=p['cost_units'] - take, cost_total=new_total.quantize(Decimal('0.01')))
        return avg


def restore_cost(product_id, qty, unit_cost):
    """Put `qty` units back at the cost they were sold at (sale removed/reduced)."""
    if unit_cost is None:
        return
    add_cost(product_id, qty, unit_cost)
