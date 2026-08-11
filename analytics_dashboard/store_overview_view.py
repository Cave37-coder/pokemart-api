# analytics_dashboard/store_overview_view.py
#
# Michael, 2026-08-11: "Can you create a page wth all of that, showing all
# those things? quick overview" -- following up on stock + total sales.
# Deliberately separate from dashboard_view.py's GA4 page: that one shows
# client-side-tracked traffic/conversion (ad-blocker-affected, "directional
# not exact" per its own disclaimer). This page pulls straight from the real
# database (PokemonProduct.stock, Order.total_price) instead, so the revenue
# and order figures here are exact, not estimates. Same staff_member_required
# + plain HTML pattern as dashboard_page for consistency.

from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.utils import timezone

from products.models import PokemonProduct
from orders.models import Order

LOW_STOCK_THRESHOLD = 5

# Cancelled orders never became real sales -- excluded from every revenue/
# order figure on this page (matches OrderAdmin's own default changelist
# view, which hides cancelled/complete... though "complete" (invoiced) IS a
# real sale and stays included here, only cancelled is excluded).
STATUS_COLORS = {
    'awaiting_payment': '#c62828', 'pending_eft': '#e65100', 'pending': '#f9a825',
    'printed': '#1565c0', 'packed': '#6a1b9a', 'booked': '#00838f',
    'ready': '#00acc1', 'collected': '#43a047', 'invoiced': '#1b5e20', 'cancelled': '#757575',
}


@staff_member_required
def store_overview_page(request):
    days = request.GET.get("days", "30")

    orders_qs = Order.objects.exclude(status='cancelled')
    if days != "all":
        try:
            days_int = int(days)
            since = timezone.now() - timezone.timedelta(days=days_int)
            orders_qs = orders_qs.filter(created_at__gte=since)
        except ValueError:
            days = "30"

    order_count = orders_qs.count()
    totals = orders_qs.aggregate(
        revenue=Sum('total_price'),
        discount_given=Sum('discount_amount'),
        discount_orders=Count('id', filter=Q(discount_amount__gt=0)),
    )
    revenue = totals['revenue'] or Decimal('0')
    discount_given = totals['discount_given'] or Decimal('0')
    discount_orders = totals['discount_orders'] or 0
    avg_order_value = (revenue / order_count) if order_count else Decimal('0')

    status_counts = dict(
        orders_qs.values('status').annotate(n=Count('id')).values_list('status', 'n')
    )

    recent_orders = list(
        orders_qs.select_related('user').order_by('-created_at')[:10]
    )

    # Stock -- deliberately NOT scoped to the days filter, this is current
    # live state, not historical.
    active_products = PokemonProduct.objects.filter(is_active=True)
    stock_totals = active_products.aggregate(
        product_count=Count('id'),
        total_units=Sum('stock'),
        out_of_stock=Count('id', filter=Q(stock=0)),
        low_stock=Count('id', filter=Q(stock__gt=0, stock__lte=LOW_STOCK_THRESHOLD)),
    )
    product_count = stock_totals['product_count'] or 0
    total_units = stock_totals['total_units'] or 0
    out_of_stock = stock_totals['out_of_stock'] or 0
    low_stock = stock_totals['low_stock'] or 0

    # Out-of-stock cards customers actually want -- reuses the same
    # wishlisted_by relation PokemonProductAdmin.wanted_by_count already
    # sorts by, just filtered down to stock=0 so it doubles as a restock
    # priority list instead of a plain report number.
    wanted_out_of_stock = list(
        active_products.filter(stock=0)
        .annotate(wanted=Count('wishlisted_by'))
        .filter(wanted__gt=0)
        .select_related('card_set')
        .order_by('-wanted')[:8]
    )

    def stat_card(label, value, color="#fff"):
        return f'''<div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:10px;padding:16px">
            <div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">{label}</div>
            <div style="font-size:26px;font-weight:800;color:{color}">{value}</div>
        </div>'''

    sales_cards = (
        stat_card("Orders", f"{order_count:,}")
        + stat_card("Revenue", f"R {revenue:,.2f}", "#4ade80")
        + stat_card("Avg Order Value", f"R {avg_order_value:,.2f}")
        + stat_card("Community Discount Given", f"R {discount_given:,.2f}" + (f" ({discount_orders} orders)" if discount_orders else ""), "#ff6b35")
    )

    stock_cards = (
        stat_card("Active Products", f"{product_count:,}")
        + stat_card("Total Stock Units", f"{total_units:,}")
        + stat_card("Out of Stock", f"{out_of_stock:,}", "#dc2626" if out_of_stock else "#4ade80")
        + stat_card(f"Low Stock (≤{LOW_STOCK_THRESHOLD})", f"{low_stock:,}", "#f59e0b" if low_stock else "#4ade80")
    )

    status_rows = ""
    total_for_pct = sum(status_counts.values()) or 1
    for status_key, status_label in Order.STATUS_CHOICES:
        if status_key == 'cancelled':
            continue
        n = status_counts.get(status_key, 0)
        pct = round(n / total_for_pct * 100) if total_for_pct else 0
        color = STATUS_COLORS.get(status_key, '#888')
        status_rows += f'''<div style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;margin-bottom:3px;font-size:12px">
                <span style="color:#fff">{status_label}</span>
                <span style="color:#888">{n:,}</span>
            </div>
            <div style="background:#12121a;border-radius:5px;height:8px;overflow:hidden">
                <div style="background:{color};height:100%;width:{pct}%;border-radius:5px"></div>
            </div>
        </div>'''

    recent_rows = ""
    for o in recent_orders:
        name = f"{o.user.first_name} {o.user.last_name}".strip() or o.user.username
        color = STATUS_COLORS.get(o.status, '#888')
        recent_rows += f'''<tr style="border-bottom:1px solid #2a2a3a">
            <td style="padding:8px 10px;font-size:12px"><a href="/admin/orders/order/{o.id}/change/" style="color:#ff6b35">#{o.id}</a></td>
            <td style="padding:8px 10px;font-size:12px;color:#ddd">{name}</td>
            <td style="padding:8px 10px;font-size:12px"><span style="background:{color};color:#fff;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:bold">{o.get_status_display()}</span></td>
            <td style="padding:8px 10px;font-size:12px;color:#888">{o.created_at.strftime('%d %b %Y %H:%M')}</td>
            <td style="padding:8px 10px;font-size:12px;text-align:right;font-weight:700;color:#fff">R {o.total_price:.2f}</td>
        </tr>'''
    if not recent_rows:
        recent_rows = '<tr><td colspan="5" style="padding:16px;text-align:center;color:#666;font-size:13px">No orders in this period.</td></tr>'

    wanted_rows = ""
    for p in wanted_out_of_stock:
        wanted_rows += f'''<tr style="border-bottom:1px solid #2a2a3a">
            <td style="padding:8px 10px;font-size:12px"><a href="/admin/products/pokemonproduct/{p.id}/change/" style="color:#ff6b35">{p.name}</a></td>
            <td style="padding:8px 10px;font-size:12px;color:#888">{p.card_set.name if p.card_set else '-'}</td>
            <td style="padding:8px 10px;font-size:12px;text-align:right;color:#f59e0b;font-weight:700">{p.wanted} wishlists</td>
        </tr>'''
    wanted_block = ""
    if wanted_rows:
        wanted_block = f'''<div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
            <h2 style="font-size:15px;margin:0 0 4px;color:#a0a0b0">Out of Stock, But Wanted</h2>
            <p style="color:#555;font-size:11px;margin:0 0 14px">Cards on customer wishlists that are currently sold out — restock priority.</p>
            <table style="width:100%;border-collapse:collapse">{wanted_rows}</table>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Store Overview - PokeBulk SA</title>
<style>
* {{ box-sizing:border-box }}
body {{ font-family:Arial,sans-serif;background:#0d0d12;color:#eee;padding:24px;margin:0 }}
select {{ background:#1a1a24;border:1px solid #2a2a3a;color:#fff;padding:8px 14px;border-radius:6px;font-size:13px }}
a {{ color:#ff6b35 }}
</style>
</head><body>
<div style="max-width:1100px;margin:0 auto">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:12px">
    <div>
      <h1 style="font-size:22px;margin:0 0 4px">Store Overview</h1>
      <div style="color:#888;font-size:13px">Live from your real order &amp; stock data (not GA4 estimates)</div>
    </div>
    <form method="get">
      <select name="days" onchange="this.form.submit()">
        <option value="7" {"selected" if days == "7" else ""}>Last 7 days</option>
        <option value="30" {"selected" if days == "30" else ""}>Last 30 days</option>
        <option value="90" {"selected" if days == "90" else ""}>Last 90 days</option>
        <option value="all" {"selected" if days == "all" else ""}>All time</option>
      </select>
    </form>
  </div>
  <div style="margin-bottom:24px"><a href="/admin/analytics-dashboard/" style="font-size:12px">→ Site traffic &amp; GA4 conversion dashboard</a></div>

  <h2 style="font-size:14px;color:#a0a0b0;margin:0 0 10px">Sales ({"all time" if days == "all" else f"last {days} days"}, excludes cancelled)</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:14px;margin-bottom:28px">
    {sales_cards}
  </div>

  <h2 style="font-size:14px;color:#a0a0b0;margin:0 0 10px">Stock (current, live)</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:14px;margin-bottom:28px">
    {stock_cards}
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px" >
    <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px">
      <h2 style="font-size:15px;margin:0 0 16px;color:#a0a0b0">Orders by Status</h2>
      {status_rows if status_rows else '<div style="color:#666;font-size:13px">No orders in this period.</div>'}
    </div>
    {wanted_block}
  </div>

  <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
    <h2 style="font-size:15px;margin:0 0 16px;color:#a0a0b0">Recent Orders</h2>
    <table style="width:100%;border-collapse:collapse">
      <thead><tr style="border-bottom:2px solid #2a2a3a">
        <th style="text-align:left;padding:6px 10px;font-size:11px;color:#888">Order</th>
        <th style="text-align:left;padding:6px 10px;font-size:11px;color:#888">Customer</th>
        <th style="text-align:left;padding:6px 10px;font-size:11px;color:#888">Status</th>
        <th style="text-align:left;padding:6px 10px;font-size:11px;color:#888">Date</th>
        <th style="text-align:right;padding:6px 10px;font-size:11px;color:#888">Total</th>
      </tr></thead>
      <tbody>{recent_rows}</tbody>
    </table>
    <div style="margin-top:14px"><a href="/admin/orders/order/" style="font-size:12px">→ View all orders</a></div>
  </div>

  <div style="color:#555;font-size:11px;text-align:center;margin-top:20px">
    Revenue/order figures are exact (pulled from the Order table). Stock figures reflect live website stock, not pos_stock (counter/POS stock).
  </div>
</div>
</body></html>'''

    return HttpResponse(html, content_type="text/html; charset=utf-8")
