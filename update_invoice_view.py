with open('orders/views.py', 'r') as f:
    content = f.read()

new_invoice = '''

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
        set_code = p.card_set.code if p.card_set else ''
        rarity = (p.rarity or '').replace('_', ' ').title()
        rows += f\'\'\'<tr style="border-bottom:1px solid #eee">
            <td style="padding:5px 8px;font-size:12px">{i}</td>
            <td style="padding:5px 8px;font-size:12px">{set_name} [{set_code}]</td>
            <td style="padding:5px 8px;font-size:12px">#{num}</td>
            <td style="padding:5px 8px;font-size:12px">{p.name}</td>
            <td style="padding:5px 8px;font-size:12px">{rarity}</td>
            <td style="padding:5px 8px;font-size:12px">{var}</td>
            <td style="padding:5px 8px;font-size:12px;text-align:center">{item.quantity}</td>
            <td style="padding:5px 8px;font-size:12px;text-align:right">R {item.price_at_purchase:.2f}</td>
            <td style="padding:5px 8px;font-size:12px;text-align:right">R {float(item.price_at_purchase) * item.quantity:.2f}</td>
        </tr>\'\'\'

    subtotal = sum(float(item.price_at_purchase) * item.quantity for item in items)
    shipping = float(order.shipping_cost or 0)
    total = subtotal + shipping
    item_count = sum(i.quantity for i in items)
    invoice_date = order.created_at.strftime(\'%d-%m-%Y\')
    invoice_num = f\'INV {order.id:08d}\'

    customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.username
    customer_email = order.user.email
    phone = getattr(order.user, \'phone_number\', \'\') or \'\'

    if order.delivery_method == \'collection\':
        delivery_label = \'Local Collection\'
        delivery_detail = \'Birchleigh North, Kempton Park\'
    elif order.pudo_locker_name:
        delivery_label = order.get_shipping_method_display()
        delivery_detail = f\'{order.pudo_locker_name}<br>{order.pudo_locker_address or ""}\'
    else:
        parts = [order.delivery_address_line1, order.delivery_address_line2,
                 order.delivery_city, order.delivery_province, order.delivery_postal_code]
        delivery_label = order.get_shipping_method_display()
        delivery_detail = \', \'.join(p for p in parts if p) or \'—\'

    waybill_row = f\'<tr><td style="color:#555;padding:3px 0;font-size:12px">Waybill</td><td style="padding:3px 0;font-size:12px;font-weight:bold">{order.waybill_number}</td></tr>\' if order.waybill_number else \'\'

    coc_notice = \'\'
    if order.payment_method == \'coc\':
        coc_notice = \'<div style="background:#fff8f0;border:1px solid #ff6b35;border-radius:6px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#333"><strong>Cash on Collection notice:</strong><br>1. Cash or card payment accepted on collection in person.<br>2. If order is to be shipped, EFT with proof of payment must be sent before dispatch.</div>\'

    eft_notice = \'\'
    if order.payment_method in [\'eft\', \'coc\']:
        eft_notice = \'<div style="background:#f5f5f5;border-radius:6px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#333"><strong>Banking details:</strong> Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Nedbank Current &nbsp;|&nbsp; Branch: 198765 &nbsp;|&nbsp; Acc: 1301474037</div>\'

    html = f\'\'\'<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{invoice_num} - PokeBulk SA</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; padding: 24px; color: #222; font-size: 13px; background: #fff; }}
  @media print {{
    body {{ padding: 0; }}
    .no-print {{ display: none !important; }}
    @page {{ margin: 12mm; size: A4; }}
  }}
  table {{ border-collapse: collapse; }}
  th {{ background: #f0f0f0; font-size: 11px; font-weight: bold; padding: 7px 8px; text-align: left; border-bottom: 2px solid #ddd; }}
</style>
</head>
<body>

<div class="no-print" style="margin-bottom:16px;display:flex;gap:8px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;cursor:pointer;font-weight:bold">Print Invoice</button>
  <button onclick="window.close()" style="background:#eee;color:#333;border:none;padding:9px 16px;border-radius:6px;font-size:13px;cursor:pointer">Close</button>
</div>

<div style="display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:14px;border-bottom:3px solid #ff6b35;margin-bottom:18px">
  <div style="display:flex;align-items:center;gap:14px">
    <div style="width:54px;height:54px;background:#0f0f18;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
      <span style="color:#ff6b35;font-weight:900;font-size:11px;line-height:1.2;text-align:center">POKE<br>BULK<br><span style="color:#fff;font-size:9px">SA</span></span>
    </div>
    <div>
      <div style="font-size:17px;font-weight:bold;color:#ff6b35">Poke Bulk SA <span style="color:#222">(Pty) Ltd</span></div>
      <div style="font-size:11px;color:#555;line-height:1.7;margin-top:2px">
        Reg. No: 2024/615040/07<br>
        4 Heloise Street, Birchleigh North, Kempton Park, 1618<br>
        Tel: 074 488 6919 (Michael V - WhatsApp) &nbsp;|&nbsp; enquiries@pokebulk.co.za<br>
        www.pokebulk.co.za
      </div>
    </div>
  </div>
  <div style="text-align:right">
    <div style="font-size:20px;font-weight:bold;color:#333">INVOICE</div>
    <div style="font-size:13px;margin-top:4px"><strong>{invoice_num}</strong></div>
    <div style="font-size:12px;color:#555;margin-top:2px">{invoice_date}</div>
    <div style="margin-top:6px;font-size:12px;color:#555">Status: <strong style="color:{"#10B981" if order.status in ["invoiced","collected","ready"] else "#F59E0B"}">{order.get_status_display()}</strong></div>
  </div>
</div>

{coc_notice}{eft_notice}

<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:18px">
  <div style="background:#f9f9f9;border-radius:6px;padding:10px 12px">
    <div style="font-size:10px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Buyer</div>
    <div style="font-weight:bold;font-size:13px">{customer_name}</div>
    <div style="font-size:12px;color:#555;margin-top:2px;line-height:1.6">
      {customer_email}<br>{phone}
    </div>
  </div>
  <div style="background:#f9f9f9;border-radius:6px;padding:10px 12px">
    <div style="font-size:10px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Delivery</div>
    <div style="font-weight:bold;font-size:13px">{delivery_label}</div>
    <div style="font-size:12px;color:#555;margin-top:2px;line-height:1.6">{delivery_detail}</div>
  </div>
  <div style="background:#f9f9f9;border-radius:6px;padding:10px 12px">
    <div style="font-size:10px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Payment</div>
    <table style="width:100%;font-size:12px">
      <tr><td style="color:#555;padding:2px 0">Method</td><td style="font-weight:bold;padding:2px 0;text-align:right">{order.get_payment_method_display()}</td></tr>
      {waybill_row}
    </table>
  </div>
</div>

<table style="width:100%;margin-bottom:16px">
  <thead>
    <tr>
      <th width="30">#</th>
      <th>Set</th>
      <th width="60">Card #</th>
      <th>Card name</th>
      <th width="100">Rarity</th>
      <th width="55">Variant</th>
      <th width="40" style="text-align:center">Qty</th>
      <th width="75" style="text-align:right">Unit</th>
      <th width="80" style="text-align:right">Total</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div style="display:flex;justify-content:flex-end;margin-bottom:20px">
  <table style="width:260px">
    <tr>
      <td style="padding:5px 8px;color:#555">Subtotal ({item_count} items)</td>
      <td style="padding:5px 8px;text-align:right">R {subtotal:.2f}</td>
    </tr>
    <tr>
      <td style="padding:5px 8px;color:#555">Shipping</td>
      <td style="padding:5px 8px;text-align:right">{"FREE" if shipping == 0 else f"R {shipping:.2f}"}</td>
    </tr>
    <tr style="font-weight:bold;font-size:15px;border-top:2px solid #ff6b35">
      <td style="padding:8px 8px">TOTAL</td>
      <td style="padding:8px 8px;text-align:right;color:#ff6b35">R {total:.2f}</td>
    </tr>
  </table>
</div>

<div style="border-top:1px solid #eee;padding-top:12px;font-size:11px;color:#888;text-align:center">
  Thank you for your order! &nbsp;|&nbsp; Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. No: 2024/615040/07 &nbsp;|&nbsp; enquiries@pokebulk.co.za &nbsp;|&nbsp; pokebulk.co.za
</div>

</body></html>\'\'\'
    return HttpResponse(html, content_type=\'text/html; charset=utf-8\')
'''

# Replace existing print_invoice or add new one
if 'def print_invoice' in content:
    # Find and replace existing
    start = content.find('\n@staff_member_required\ndef print_invoice')
    if start == -1:
        start = content.find('\ndef print_invoice')
    end = content.find('\n@', start + 10)
    if end == -1:
        end = len(content)
    content = content[:start] + new_invoice + content[end:]
    print("Invoice view replaced")
else:
    content = content + new_invoice
    print("Invoice view added")

with open('orders/views.py', 'w') as f:
    f.write(content)
