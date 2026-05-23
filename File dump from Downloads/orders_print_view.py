# Add to orders/views.py

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template import Template, Context
from .models import Order

PRINT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Order #{{ order_id }} — PokéBulk SA</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: Arial, sans-serif; font-size: 13px; color: #000; padding: 20px; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  .header { display: flex; justify-content: space-between; margin-bottom: 16px; border-bottom: 2px solid #000; padding-bottom: 12px; }
  .meta { font-size: 12px; color: #444; margin-top: 4px; }
  .section { margin-bottom: 12px; }
  .section h3 { font-size: 13px; font-weight: bold; background: #f0f0f0; padding: 4px 8px; border-left: 3px solid #ff6b35; margin-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
  th { background: #eee; text-align: left; padding: 4px 8px; font-size: 11px; border-bottom: 1px solid #ccc; }
  td { padding: 4px 8px; border-bottom: 1px solid #eee; font-size: 12px; }
  tr:last-child td { border-bottom: none; }
  .variant { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 10px; font-weight: bold; }
  .N  { background: #e8e8e8; color: #333; }
  .H  { background: #fff3cd; color: #856404; }
  .RH { background: #e8e4ff; color: #4c3d99; }
  .total-row { font-weight: bold; background: #f9f9f9; }
  .footer { margin-top: 20px; border-top: 1px solid #ccc; padding-top: 12px; font-size: 11px; color: #666; }
  .delivery-box { border: 1px solid #ccc; padding: 10px; border-radius: 4px; margin-bottom: 16px; font-size: 12px; }
  .delivery-box h3 { font-size: 13px; margin-bottom: 6px; }
  .checked { font-size: 16px; }
  @media print {
    .no-print { display: none; }
    body { padding: 0; }
  }
</style>
</head>
<body>

<div class="no-print" style="margin-bottom:16px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-size:14px;cursor:pointer">🖨 Print</button>
  <button onclick="window.close()" style="margin-left:8px;padding:8px 20px;border-radius:6px;border:1px solid #ccc;cursor:pointer">Close</button>
</div>

<div class="header">
  <div>
    <h1>⚡ PokéBulk SA — Packing Slip</h1>
    <div class="meta">Order #{{ order_id }} &nbsp;|&nbsp; {{ created_at }} &nbsp;|&nbsp; {{ item_count }} cards</div>
    <div class="meta">Customer: <strong>{{ username }}</strong> ({{ email }})</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:24px;font-weight:bold;color:#ff6b35">R {{ total_price }}</div>
    <div class="meta">{{ delivery_method }}</div>
    <div class="meta">Status: {{ status }}</div>
  </div>
</div>

<div class="delivery-box">
  <h3>📦 Delivery Details</h3>
  {{ delivery_info }}
</div>

{% if customer_note %}
<div class="delivery-box" style="border-color:#ff6b35">
  <h3>📝 Customer Note</h3>
  {{ customer_note }}
</div>
{% endif %}

<h2 style="margin-bottom:8px;font-size:15px">Cards to Pack — Grouped by Set</h2>

{% for set_name, cards in sets %}
<div class="section">
  <h3>{{ set_name }} ({{ cards|length }} card{% if cards|length != 1 %}s{% endif %})</h3>
  <table>
    <thead>
      <tr>
        <th width="60">#</th>
        <th width="50">Card #</th>
        <th>Card Name</th>
        <th width="70">Variant</th>
        <th width="40">Qty</th>
        <th width="80">Price</th>
        <th width="30">✓</th>
      </tr>
    </thead>
    <tbody>
      {% for card in cards %}
      <tr>
        <td>{{ forloop.counter }}</td>
        <td>{{ card.card_number }}</td>
        <td>{{ card.name }}</td>
        <td><span class="variant {{ card.variant }}">{{ card.variant }}</span></td>
        <td>{{ card.quantity }}</td>
        <td>R {{ card.price }}</td>
        <td><span class="checked">□</span></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endfor %}

<table style="margin-top:8px">
  <tr class="total-row">
    <td colspan="5" style="text-align:right;padding:8px">Subtotal</td>
    <td style="padding:8px">R {{ subtotal }}</td>
    <td></td>
  </tr>
  <tr class="total-row">
    <td colspan="5" style="text-align:right;padding:8px">Shipping ({{ shipping_method }})</td>
    <td style="padding:8px">R {{ shipping_cost }}</td>
    <td></td>
  </tr>
  <tr class="total-row" style="font-size:15px">
    <td colspan="5" style="text-align:right;padding:8px">TOTAL</td>
    <td style="padding:8px;color:#ff6b35">R {{ total_price }}</td>
    <td></td>
  </tr>
</table>

<div class="footer">
  Printed: {{ printed_at }} &nbsp;|&nbsp; PokéBulk SA — Birchleigh North, Kempton Park &nbsp;|&nbsp; enquiries@pokebulk.co.za
</div>

</body>
</html>
"""

@staff_member_required
def print_order(request, order_id):
    from django.utils import timezone
    from itertools import groupby

    order = get_object_or_404(Order, id=order_id)
    items = order.items.select_related(
        'product', 'product__card_set', 'product__card_set__era'
    ).order_by('product__card_set__era__code', 'product__card_set__name', 'product__card_number')

    # Group by set
    sets_data = []
    for set_name, group in groupby(items, key=lambda i: i.product.card_set.name):
        cards = []
        for item in group:
            p = item.product
            # Normalize card number for display
            num = str(p.card_number or '').zfill(3) if str(p.card_number or '').isdigit() else str(p.card_number or '—')
            cards.append({
                'card_number': num,
                'name': p.name,
                'variant': p.variant_override or 'N',
                'quantity': item.quantity,
                'price': f"{item.price_at_purchase:.2f}",
            })
        sets_data.append((set_name, cards))

    # Delivery info
    if order.delivery_method == 'collection':
        delivery_info = "LOCAL COLLECTION — Birchleigh North, Kempton Park"
    else:
        parts = [
            order.delivery_address_line1,
            order.delivery_address_line2,
            order.delivery_city,
            order.delivery_province,
            order.delivery_postal_code,
        ]
        delivery_info = ", ".join(p for p in parts if p)
        if not delivery_info:
            delivery_info = order.customer_note or "— no address provided —"

    subtotal = sum(item.price_at_purchase * item.quantity for item in order.items.all())
    shipping = order.total_price - subtotal

    context = {
        'order_id': order.id,
        'created_at': order.created_at.strftime('%d %b %Y %H:%M'),
        'printed_at': timezone.now().strftime('%d %b %Y %H:%M'),
        'username': order.user.username,
        'email': order.user.email,
        'item_count': sum(i.quantity for i in order.items.all()),
        'total_price': f"{order.total_price:.2f}",
        'subtotal': f"{subtotal:.2f}",
        'shipping_cost': f"{shipping:.2f}",
        'shipping_method': order.delivery_method,
        'status': order.get_status_display(),
        'delivery_method': order.get_delivery_method_display(),
        'delivery_info': delivery_info,
        'customer_note': order.customer_note,
        'sets': sets_data,
    }

    # Simple template rendering
    html = PRINT_TEMPLATE
    html = html.replace('{{ order_id }}', str(context['order_id']))
    html = html.replace('{{ created_at }}', context['created_at'])
    html = html.replace('{{ printed_at }}', context['printed_at'])
    html = html.replace('{{ username }}', context['username'])
    html = html.replace('{{ email }}', context['email'])
    html = html.replace('{{ item_count }}', str(context['item_count']))
    html = html.replace('{{ total_price }}', context['total_price'])
    html = html.replace('{{ subtotal }}', context['subtotal'])
    html = html.replace('{{ shipping_cost }}', context['shipping_cost'])
    html = html.replace('{{ shipping_method }}', context['shipping_method'])
    html = html.replace('{{ status }}', context['status'])
    html = html.replace('{{ delivery_method }}', context['delivery_method'])
    html = html.replace('{{ delivery_info }}', context['delivery_info'])
    html = html.replace('{{ customer_note }}', context['customer_note'] or '')

    # Build sets HTML
    sets_html = ''
    for set_name, cards in sets_data:
        rows = ''
        for i, card in enumerate(cards, 1):
            rows += f"""
            <tr>
              <td>{i}</td>
              <td>{card['card_number']}</td>
              <td>{card['name']}</td>
              <td><span class="variant {card['variant']}">{card['variant']}</span></td>
              <td>{card['quantity']}</td>
              <td>R {card['price']}</td>
              <td><span class="checked">□</span></td>
            </tr>"""

        plural = 's' if len(cards) != 1 else ''
        sets_html += f"""
        <div class="section">
          <h3>{set_name} ({len(cards)} card{plural})</h3>
          <table>
            <thead>
              <tr>
                <th width="40">#</th>
                <th width="60">Card #</th>
                <th>Card Name</th>
                <th width="70">Variant</th>
                <th width="40">Qty</th>
                <th width="80">Price</th>
                <th width="30">✓</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    # Replace sets block
    import re
    html = re.sub(r'{%\s*for set_name.*?{%\s*endfor\s*%}', sets_html, html, flags=re.DOTALL)

    # Clean up remaining template tags
    html = re.sub(r'{%.*?%}', '', html)
    html = re.sub(r'\{\{.*?\}\}', '', html)

    return HttpResponse(html)
