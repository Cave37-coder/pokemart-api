"""
Manual invoice HTML + PDF builder.

Deliberately uses table-based layout only (no flexbox/grid) so the exact
same HTML renders correctly both in a browser (Print/View Invoice) and
through xhtml2pdf (Download PDF) — xhtml2pdf's rendering engine does not
support CSS flexbox or grid.

Requires: pip install xhtml2pdf --break-system-packages
Add "xhtml2pdf" to requirements.txt before deploying to Railway.
"""

VARIANT_LABEL_FULL = {
    'N': 'Normal', 'H': 'Holo', 'RH': 'Reverse Holo',
    'PB': 'Poke Ball', 'MB': 'Master Ball', 'LB': 'Love Ball',
    'FB': 'Friend Ball', 'QB': 'Quick Ball', 'UB': 'Ultra Ball',
    'DB': 'Dusk Ball', 'TR': 'Team Rocket', 'SE': 'Secret',
    'PBP': 'PB Pattern', 'MBP': 'MB Pattern',
    'CC': 'Code Card', 'TT': 'Trick or Trade',
}


def build_manual_invoice_html(invoice, show_controls=True):
    items = list(invoice.items.select_related('product', 'product__card_set').all())

    rows = ''
    for i, item in enumerate(items, 1):
        set_name = item.set_name or '-'
        card_number = item.card_number or '--'
        variant_label = VARIANT_LABEL_FULL.get(item.variant, item.variant or '-')
        name = item.description or (item.product.name if item.product else 'Item')
        unit_price = float(item.unit_price or 0)
        line_total = float(item.line_total)
        rows += f'''<tr>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{i}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{set_name}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">#{card_number}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{name}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee">{variant_label}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee;text-align:center">{item.quantity}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee;text-align:right">R {unit_price:.2f}</td>
            <td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #eee;text-align:right">R {line_total:.2f}</td>
        </tr>'''

    subtotal = float(invoice.subtotal)
    discount_percent = float(invoice.discount_percent or 0)
    discount_amount = float(invoice.discount_amount)
    shipping = float(invoice.shipping_cost or 0)
    total = float(invoice.total)
    item_count = invoice.item_count
    invoice_date = invoice.created_at.strftime('%d-%m-%Y')

    delivery_block = invoice.delivery_note.replace('\n', '<br>') if invoice.delivery_note else '-'
    payment_status = 'EFT Confirmed' if invoice.eft_confirmed else 'Awaiting EFT'
    payment_color = '#2e7d32' if invoice.eft_confirmed else '#e65100'

    discount_row = ''
    if discount_percent:
        discount_row = f'''<tr><td style="padding:3px 8px;color:#2e7d32">Discount ({discount_percent:g}%)</td><td style="padding:3px 8px;text-align:right;color:#2e7d32">-R {discount_amount:.2f}</td></tr>'''

    controls_html = '''<table width="100%" style="margin-bottom:16px"><tr><td>
      <span class="no-print" style="background:#ff6b35;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;font-weight:bold">
      <a href="javascript:window.print()" style="color:#fff;text-decoration:none">Print Invoice</a></span>
      &nbsp;
      <span class="no-print" style="background:#eee;color:#333;border:none;padding:9px 16px;border-radius:6px;font-size:13px">
      <a href="javascript:window.close()" style="color:#333;text-decoration:none">Close</a></span>
    </td></tr></table>''' if show_controls else ''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{invoice.invoice_number} - PokeBulk SA</title>
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
        4 Heloise Street, Birchleigh North, Kempton Park, 1618<br>
        Tel: 074 488 6919 &nbsp;|&nbsp; enquiries@pokebulk.co.za
      </div>
    </td>
    <td style="width:40%;text-align:right;vertical-align:top">
      <div style="font-size:20px;font-weight:bold;color:#333">INVOICE</div>
      <div style="font-size:13px;margin-top:3px"><strong>{invoice.invoice_number}</strong></div>
      <div style="font-size:11px;color:#555;margin-top:2px">{invoice_date}</div>
      <div style="margin-top:5px;font-size:11px;color:{payment_color};font-weight:bold">{payment_status}</div>
    </td>
  </tr>
</table>

<table style="background:#f5f5f5;border-radius:6px;padding:8px 14px;margin-bottom:12px">
  <tr><td style="padding:6px 10px;font-size:11px;color:#333"><strong>Payment:</strong> EFT / Bank Transfer only &nbsp;|&nbsp; Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Nedbank Current &nbsp;|&nbsp; Branch: 198765 &nbsp;|&nbsp; Acc: 1301474037</td></tr>
</table>

<table style="margin-bottom:14px">
  <tr>
    <td style="width:50%;vertical-align:top;padding-right:8px">
      <table style="background:#f9f9f9;border-radius:6px">
        <tr><td style="padding:8px 10px">
          <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Buyer</div>
          <div style="font-weight:bold;font-size:12px">{invoice.customer_name}</div>
          <div style="font-size:11px;color:#555;margin-top:2px;line-height:1.3">{invoice.customer_email or ''}<br>{invoice.customer_phone or ''}</div>
        </td></tr>
      </table>
    </td>
    <td style="width:50%;vertical-align:top;padding-left:8px">
      <table style="background:#f9f9f9;border-radius:6px">
        <tr><td style="padding:8px 10px">
          <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Delivery</div>
          <div style="font-size:11px;color:#555;line-height:1.3">{delivery_block}</div>
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
      <tr><td style="padding:3px 8px;color:#555">Subtotal ({item_count} items)</td><td style="padding:3px 8px;text-align:right">R {subtotal:.2f}</td></tr>
      {discount_row}
      <tr><td style="padding:3px 8px;color:#555">Shipping</td><td style="padding:3px 8px;text-align:right">{"FREE" if shipping == 0 else f"R {shipping:.2f}"}</td></tr>
      <tr><td style="padding:6px 8px;font-weight:bold;font-size:14px;border-top:2px solid #ff6b35">TOTAL</td><td style="padding:6px 8px;text-align:right;font-weight:bold;font-size:14px;border-top:2px solid #ff6b35;color:#ff6b35">R {total:.2f}</td></tr>
    </table>
  </td></tr>
</table>

<table style="border-top:1px solid #eee">
  <tr><td style="padding-top:8px;font-size:10px;color:#888;text-align:center">
    Thank you! &nbsp;|&nbsp; Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. No: 2024/615040/07 &nbsp;|&nbsp; enquiries@pokebulk.co.za
  </td></tr>
</table>
</body></html>'''
    return html


def html_to_pdf(html):
    """Converts invoice HTML to PDF bytes using xhtml2pdf (pure Python,
    no native/GTK dependency — installs cleanly on Windows and Railway)."""
    from io import BytesIO
    from xhtml2pdf import pisa

    result = BytesIO()
    pisa.CreatePDF(src=html, dest=result, encoding='utf-8')
    return result.getvalue()
