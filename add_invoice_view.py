with open('orders/views.py', 'r') as f:
    content = f.read()

invoice_view = '''

@staff_member_required
def print_invoice(request, order_id):
    from django.utils import timezone
    order = get_object_or_404(Order, id=order_id)
    items = list(order.items.select_related(
        'product', 'product__card_set', 'product__card_set__era'
    ).order_by('product__card_set__name', 'product__card_number'))

    rows = ''
    for i, item in enumerate(items, 1):
        p = item.product
        num = str(p.card_number or '').zfill(3)
        var = p.variant_override or 'N'
        set_name = p.card_set.name if p.card_set else '—'
        rows += f\'\'\'<tr style="border-bottom:1px solid #eee">
            <td style="padding:6px 8px;font-size:12px">{i}</td>
            <td style="padding:6px 8px;font-size:12px">{set_name}</td>
            <td style="padding:6px 8px;font-size:12px">#{num}</td>
            <td style="padding:6px 8px;font-size:12px">{p.name}</td>
            <td style="padding:6px 8px;font-size:12px;text-align:center">{var}</td>
            <td style="padding:6px 8px;font-size:12px;text-align:center">{item.quantity}</td>
            <td style="padding:6px 8px;font-size:12px;text-align:right">R {item.price_at_purchase:.2f}</td>
            <td style="padding:6px 8px;font-size:12px;text-align:right">R {item.price_at_purchase * item.quantity:.2f}</td>
        </tr>\'\'\'

    subtotal = sum(item.price_at_purchase * item.quantity for item in items)
    shipping = float(order.shipping_cost or 0)
    total = subtotal + shipping
    item_count = sum(i.quantity for i in items)
    printed_at = timezone.now().strftime(\'%d %b %Y %H:%M\')

    customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.username
    customer_email = order.user.email

    if order.delivery_method == \'collection\':
        delivery_info = \'<strong>Collection</strong> — Birchleigh North, Kempton Park\'
    elif order.pudo_locker_name:
        delivery_info = f\'<strong>{order.get_shipping_method_display()}</strong><br>{order.pudo_locker_name}<br>{order.pudo_locker_address or ""}\'
    else:
        parts = [order.delivery_address_line1, order.delivery_address_line2,
                 order.delivery_city, order.delivery_province, order.delivery_postal_code]
        delivery_info = \'<strong>\' + order.get_shipping_method_display() + \'</strong><br>\' + \', \'.join(p for p in parts if p)

    payment_info = order.get_payment_method_display()
    if order.waybill_number:
        waybill_row = f\'<tr><td style="padding:4px 0;color:#555;font-size:12px">Waybill</td><td style="padding:4px 0;font-size:12px;font-weight:600">{order.waybill_number}</td></tr>\'
    else:
        waybill_row = \'\'

    html = f\'\'\'<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Invoice #{order.id} - PokeBulk SA</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; font-size: 13px; }}
  @media print {{
    body {{ padding: 0; }}
    .no-print {{ display: none; }}
    @page {{ margin: 15mm; }}
  }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #ff6b35; }}
  .logo {{ font-size: 22px; font-weight: 900; color: #ff6b35; }}
  .logo span {{ color: #333; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #f5f5f5; padding: 8px; text-align: left; font-size: 11px; border-bottom: 2px solid #ddd; }}
  .info-box {{ background: #f9f9f9; border: 1px solid #eee; border-radius: 6px; padding: 12px; }}
  .total-row {{ font-weight: 700; font-size: 14px; background: #fff8f5; }}
</style>
</head>
<body>

<div class="no-print" style="margin-bottom:16px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:10px 20px;border-radius:6px;font-size:14px;cursor:pointer;font-weight:bold">🖨 Print Invoice</button>
</div>

<div class="header">
  <div>
    <div class="logo">Poke<span>Bulk</span> <span style="color:#ff6b35">SA</span></div>
    <div style="font-size:11px;color:#555;margin-top:4px">Straight outta Kempton Park</div>
    <div style="font-size:11px;color:#555">4 Heliose Street, Birchleigh North, 1619</div>
    <div style="font-size:11px;color:#555">enquiries@pokebulk.co.za | 074 488 6919</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:20px;font-weight:900;color:#333">INVOICE</div>
    <div style="font-size:13px;margin-top:4px">Order <strong>#{order.id}</strong></div>
    <div style="font-size:11px;color:#555">{order.created_at.strftime(\'%d %b %Y\')}</div>
    <div style="font-size:11px;color:#555">Printed: {printed_at}</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:20px">
  <div class="info-box">
    <div style="font-size:10px;color:#888;font-weight:700;margin-bottom:6px;text-transform:uppercase">Bill To</div>
    <div style="font-weight:600">{customer_name}</div>
    <div style="color:#555;font-size:12px">{customer_email}</div>
    <div style="color:#555;font-size:12px">{order.user.phone_number if hasattr(order.user, "phone_number") else ""}</div>
  </div>
  <div class="info-box">
    <div style="font-size:10px;color:#888;font-weight:700;margin-bottom:6px;text-transform:uppercase">Delivery</div>
    <div style="font-size:12px">{delivery_info}</div>
  </div>
  <div class="info-box">
    <div style="font-size:10px;color:#888;font-weight:700;margin-bottom:6px;text-transform:uppercase">Payment</div>
    <table style="font-size:12px">
      <tr><td style="padding:4px 0;color:#555">Method</td><td style="padding:4px 0;font-weight:600;padding-left:8px">{payment_info}</td></tr>
      <tr><td style="padding:4px 0;color:#555">Status</td><td style="padding:4px 0;font-weight:600;padding-left:8px;color:{"#10B981" if order.status not in ["pending","awaiting_payment","pending_eft"] else "#F59E0B"}">{order.get_status_display()}</td></tr>
      {waybill_row}
    </table>
  </div>
</div>

<table style="margin-bottom:16px">
  <thead>
    <tr>
      <th width="30">#</th>
      <th>Set</th>
      <th width="60">Card #</th>
      <th>Card Name</th>
      <th width="60" style="text-align:center">Variant</th>
      <th width="40" style="text-align:center">Qty</th>
      <th width="80" style="text-align:right">Unit Price</th>
      <th width="90" style="text-align:right">Total</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div style="display:flex;justify-content:flex-end">
  <table style="width:280px;border-top:2px solid #eee">
    <tr>
      <td style="padding:6px 8px;color:#555">Subtotal ({item_count} items)</td>
      <td style="padding:6px 8px;text-align:right">R {subtotal:.2f}</td>
    </tr>
    <tr>
      <td style="padding:6px 8px;color:#555">Shipping ({order.get_shipping_method_display()})</td>
      <td style="padding:6px 8px;text-align:right">{"FREE" if shipping == 0 else f"R {shipping:.2f}"}</td>
    </tr>
    <tr class="total-row">
      <td style="padding:8px;border-top:2px solid #ff6b35">TOTAL</td>
      <td style="padding:8px;text-align:right;border-top:2px solid #ff6b35;color:#ff6b35;font-size:16px">R {total:.2f}</td>
    </tr>
  </table>
</div>

<div style="margin-top:24px;padding-top:16px;border-top:1px solid #eee;font-size:11px;color:#888;text-align:center">
  Thank you for your order! | PokeBulk SA | enquiries@pokebulk.co.za | pokebulk.co.za
</div>

</body></html>\'\'\'
    return HttpResponse(html, content_type=\'text/html; charset=utf-8\')
'''

# Add before the last line or after print_order
if 'def print_invoice' not in content:
    content = content + invoice_view
    print("Invoice view added")
else:
    print("Already exists")

with open('orders/views.py', 'w') as f:
    f.write(content)
