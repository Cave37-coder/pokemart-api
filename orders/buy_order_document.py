"""
Buy order HTML + PDF builder. Mirrors manual_invoice.py's structure and
branding exactly (same table-based layout for xhtml2pdf compatibility,
same business header, same fonts/colors) so a buy-in receipt looks like
it belongs to the same business as a sales invoice -- just labeled and
laid out for the reverse transaction (paying a seller, not charging a
buyer).

Deliberately does NOT include BuyOrder.internal_note anywhere in this
document -- that field is explicitly for Michael's own records only, per
its own model docstring ("not shown to the seller"). Nothing here reads
that field.

Requires: pip install xhtml2pdf --break-system-packages (already a
dependency for manual_invoice.py, no new requirements.txt entry needed).
"""

METHOD_LABELS = {'eft': 'EFT', 'cash': 'Cash', 'card': 'Card'}


def build_buy_order_html(buy_order, show_controls=True):
    items = list(buy_order.items.select_related('product').all())

    rows = ''
    for i, item in enumerate(items, 1):
        set_name = item.set_name or '-'
        card_number = item.card_number or '--'
        variant = item.variant or '-'
        name = item.description or (item.product.name if item.product else 'Item')
        unit_price = float(item.unit_price or 0)
        line_total = float(item.line_total)
        rows += f'''<tr>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{i}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{set_name}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">#{card_number}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{name}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{variant}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee;text-align:center">{item.quantity}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee;text-align:right">R {unit_price:.2f}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee;text-align:right">R {line_total:.2f}</td>
        </tr>'''

    total = float(buy_order.total)
    item_count = buy_order.item_count
    buy_date = buy_order.created_at.strftime('%d-%m-%Y')

    if buy_order.payment_made:
        method_label = METHOD_LABELS.get(buy_order.payment_method, '')
        payment_status = f'{method_label} Paid' if method_label else 'Payment Made'
        payment_color = '#2e7d32'
    else:
        payment_status = 'Payment Pending'
        payment_color = '#e65100'

    controls_html = '''<table width="100%" style="margin-bottom:16px"><tr><td>
      <span class="no-print" style="background:#ff6b35;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;font-weight:bold">
      <a href="javascript:window.print()" style="color:#fff;text-decoration:none">Print Receipt</a></span>
      &nbsp;
      <span class="no-print" style="background:#eee;color:#333;border:none;padding:9px 16px;border-radius:6px;font-size:13px">
      <a href="javascript:window.close()" style="color:#333;text-decoration:none">Close</a></span>
    </td></tr></table>''' if show_controls else ''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{buy_order.buy_number} - PokeBulk SA</title>
<style>
* {{ box-sizing:border-box;margin:0;padding:0 }}
body {{ font-family:Arial,sans-serif;padding:16px;color:#222;font-size:12px;line-height:1.3 }}
table {{ border-collapse:collapse;width:100% }}
th {{ background:#f0f0f0;font-size:10px;font-weight:bold;padding:5px 8px;text-align:left;border-bottom:2px solid #ddd }}
@media print {{ .no-print {{ display:none !important }} @page {{ margin:10mm;size:A4 }} }}
</style>
</head><body>
{controls_html}
<table style="border-bottom:3px solid #ff6b35;margin-bottom:14px;padding-bottom:10px">
  <tr>
    <td style="width:60%;vertical-align:top">
      <div style="font-size:17px;font-weight:bold;color:#ff6b35">Poke Bulk SA <span style="color:#222">(Pty) Ltd</span></div>
      <div style="font-size:11px;color:#555;line-height:1.4;margin-top:3px">
        Reg. No: 2024/615040/07<br>
        Unit 4, Sunkist Village, 11 Heliose Street, Birchleigh North, Kempton Park, 1618<br>
        Tel: 074 488 6919 &nbsp;|&nbsp; enquiries@pokebulk.co.za
      </div>
    </td>
    <td style="width:40%;text-align:right;vertical-align:top">
      <div style="font-size:20px;font-weight:bold;color:#333">BUY-IN RECEIPT</div>
      <div style="font-size:13px;margin-top:3px"><strong>{buy_order.buy_number}</strong></div>
      <div style="font-size:11px;color:#555;margin-top:2px">{buy_date}</div>
      <div style="margin-top:5px;font-size:11px;color:{payment_color};font-weight:bold">{payment_status}</div>
    </td>
  </tr>
</table>

<table style="margin-bottom:14px">
  <tr>
    <td style="width:50%;vertical-align:top">
      <table style="background:#f9f9f9;border-radius:6px">
        <tr><td style="padding:8px 10px">
          <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Seller</div>
          <div style="font-weight:bold;font-size:12px">{buy_order.seller_name}</div>
          <div style="font-size:11px;color:#555;margin-top:2px;line-height:1.3">{buy_order.seller_email or ''}<br>{buy_order.seller_phone or ''}</div>
        </td></tr>
      </table>
    </td>
  </tr>
</table>

<table style="margin-bottom:10px">
  <thead><tr>
    <th width="30">#</th><th>Set</th><th width="60">Card #</th><th>Item</th>
    <th width="80">Variant</th><th width="40" style="text-align:center">Qty</th>
    <th width="75" style="text-align:right">Unit</th><th width="80" style="text-align:right">Total</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>

<table style="margin-bottom:14px">
  <tr><td style="width:60%"></td><td style="width:40%">
    <table>
      <tr><td style="padding:3px 8px;color:#555">Items ({item_count})</td><td style="padding:3px 8px;text-align:right">&nbsp;</td></tr>
      <tr><td style="padding:6px 8px;font-weight:bold;font-size:14px;border-top:2px solid #ff6b35">TOTAL PAID</td><td style="padding:6px 8px;text-align:right;font-weight:bold;font-size:14px;border-top:2px solid #ff6b35;color:#ff6b35">R {total:.2f}</td></tr>
    </table>
  </td></tr>
</table>

<table style="border-top:1px solid #eee;margin-top:6px">
  <tr><td style="padding-top:10px;text-align:center">
    <img src="https://pokebulk.co.za/pokebulk-logo.png" alt="PokeBulk SA" style="height:28px" />
  </td></tr>
  <tr><td style="padding-top:6px;font-size:10px;color:#888;text-align:center">
    Thank you for selling to us! &nbsp;|&nbsp; Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. No: 2024/615040/07 &nbsp;|&nbsp; enquiries@pokebulk.co.za
  </td></tr>
</table>
</body></html>'''
    return html


def html_to_pdf(html):
    """Converts buy order HTML to PDF bytes using xhtml2pdf -- same helper
    as manual_invoice.py, duplicated here rather than imported so this
    file has no dependency on the invoice module and can be deployed/
    edited independently."""
    from io import BytesIO
    from xhtml2pdf import pisa

    result = BytesIO()
    pisa.CreatePDF(src=html, dest=result, encoding='utf-8')
    return result.getvalue()
