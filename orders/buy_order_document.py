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


def build_buy_order_html(buy_order, show_controls=True, mode='internal'):
    """mode='client'   -> receipt for the seller: card, condition, qty, TCG price,
                          the rate bought at (% of TCG) and the price paid. No
                          sell price / profit.
       mode='internal' -> our stock sheet: same plus the sell-at price and
                          profit per card (inventory tracking)."""
    client = (mode == 'client')
    items = list(buy_order.items.select_related('product').all())
    td = 'padding:3px 8px;font-size:11px;border-bottom:1px solid #eee'

    rows = ''
    tot_qty = 0
    tot_tcg = tot_paid = tot_sell = tot_profit = tot_sell_cost = 0.0
    premium = bool(getattr(buy_order, 'premium_accepted', False))
    # Internal sheet colours (tinted backgrounds so they still read in B&W print):
    # real rate green <= 80% of TCG, amber above (blue if the premium was accepted
    # on purpose); profit green = gaining, red = losing.
    GREEN, RED, AMBER, BLUE = '#d9f2dd;color:#1b5e20', '#fbd5d5;color:#b71c1c', '#fff0c2;color:#8a5a00', '#d6ecfb;color:#0b5394'
    for i, item in enumerate(items, 1):
        set_name = item.set_name or '-'
        card_number = item.card_number or '--'
        variant = item.variant or '-'
        name = item.description or (item.product.name if item.product else 'Item')
        unit_price = float(item.unit_price or 0)
        line_total = float(item.line_total)
        condition = item.condition or 'NM'
        tcg = float(item.tcg_price) if item.tcg_price else None
        tcg_txt = f'R {tcg:.2f}' if tcg else '-'
        rate_txt = f'{unit_price / tcg * 100:.0f}%' if tcg else '-'
        tot_qty += item.quantity
        tot_tcg += (tcg or 0) * item.quantity
        tot_paid += line_total
        if item.sell_price:
            tot_sell += float(item.sell_price) * item.quantity
        sell_cell = ''
        if not client:
            real = float(buy_order.effective_unit_cost(item))
            if tcg:
                rr = real / tcg * 100
                rate_txt = f'{rr:.0f}%'
                rate_bg = GREEN if rr <= 80 else (BLUE if premium else AMBER)
                rate_style = f';background:{rate_bg};font-weight:bold'
            else:
                rate_style = ''
            sell = f'R {float(item.sell_price):.2f}' if item.sell_price else '-'
            if item.sell_price:
                sp = float(item.sell_price)
                profit = sp - real
                margin = profit / sp * 100 if sp else 0
                tot_profit += profit * item.quantity
                tot_sell_cost += sp * item.quantity
                pbg = GREEN if profit >= 0 else RED
                profit_cells = (f'<td style="{td};text-align:right;background:{pbg};font-weight:bold">{profit:+.2f}</td>'
                                f'<td style="{td};text-align:right;background:{pbg};font-weight:bold">{margin:.0f}%</td>')
            else:
                profit_cells = f'<td style="{td};text-align:right">-</td><td style="{td};text-align:right">-</td>'
            sell_cell = f'<td style="{td};text-align:right">{sell}</td>{profit_cells}'
        else:
            rate_style = ''
        rows += f'''<tr>
            <td style="{td}">{i}</td>
            <td style="{td}">{set_name}</td>
            <td style="{td}">#{card_number}</td>
            <td style="{td}">{name}</td>
            <td style="{td}">{variant}</td>
            <td style="{td}">{condition}</td>
            <td style="{td};text-align:center">{item.quantity}</td>
            <td style="{td};text-align:right">{tcg_txt}</td>
            <td style="{td};text-align:right{rate_style}">{rate_txt}</td>
            <td style="{td};text-align:right">R {unit_price:.2f}</td>
            {sell_cell}
            <td style="{td};text-align:right">R {line_total:.2f}</td>
        </tr>'''

    # Stock-sheet totals row (internal only): every numeric column summed.
    # Price columns are extended (price x qty), so Paid ea. adds up to the
    # same figure as the Total column and the TOTAL PAID box below.
    totals_row = ''
    if not client:
        tt = 'padding:5px 8px;font-size:11px;font-weight:bold;border-top:2px solid #ff6b35;background:#fafafa'
        real_total = float(buy_order.amount_paid) if getattr(buy_order, 'amount_paid', None) is not None else tot_paid
        overall_rate = f'{real_total / tot_tcg * 100:.0f}%' if tot_tcg else '-'
        pc = '#1b5e20' if tot_profit >= 0 else '#b71c1c'
        margin_tot = (tot_profit / tot_sell_cost * 100) if tot_sell_cost else 0
        lab = 'display:block;font-size:8px;font-weight:normal;color:#777;text-transform:uppercase;letter-spacing:0.03em;margin-bottom:1px;white-space:nowrap'
        nw = 'white-space:nowrap'
        totals_row = f'''<tfoot><tr>
            <td colspan="6" style="{tt};text-align:right;font-size:13px">TOTALS</td>
            <td style="{tt};text-align:center"><span style="{lab}">Qty</span>{tot_qty}</td>
            <td style="{tt};text-align:right;{nw}"><span style="{lab}">TCG value</span>R {tot_tcg:.2f}</td>
            <td style="{tt};text-align:right;{nw}"><span style="{lab}">Real rate</span>{overall_rate}</td>
            <td style="{tt};text-align:right;{nw}"><span style="{lab}">Paid (invoice)</span>R {tot_paid:.2f}</td>
            <td style="{tt};text-align:right;{nw}"><span style="{lab}">Sell value</span>R {tot_sell:.2f}</td>
            <td style="{tt};text-align:right;{nw};color:{pc}"><span style="{lab}">Profit</span>R {tot_profit:+.2f}</td>
            <td style="{tt};text-align:right;{nw};color:{pc}"><span style="{lab}">Margin</span>{margin_tot:.0f}%</td>
            <td style="{tt};text-align:right;{nw}"><span style="{lab}">Total paid</span>R {tot_paid:.2f}</td>
        </tr></tfoot>'''
    legend = '' if client else (
        '<div style="font-size:10px;color:#555;margin-bottom:10px">'
        '<b>Colour key:</b> Real rate = what we really paid as % of TCG (after the actual amount paid). '
        '<span style="background:#d9f2dd;color:#1b5e20;padding:1px 6px">green</span> at or under 80% / profit &nbsp;'
        '<span style="background:#fff0c2;color:#8a5a00;padding:1px 6px">amber</span> over 80% &nbsp;'
        '<span style="background:#d6ecfb;color:#0b5394;padding:1px 6px">blue</span> over 80%, premium accepted &nbsp;'
        '<span style="background:#fbd5d5;color:#b71c1c;padding:1px 6px">red</span> selling below real cost.</div>')
    sell_header = '' if client else ('<th width="70" style="text-align:right">Sell at</th>'
                                     '<th width="62" style="text-align:right">Profit ea.</th>'
                                     '<th width="50" style="text-align:right">Margin</th>')
    rate_header = 'Rate' if client else 'Real rate'
    doc_title = 'BUY-IN RECEIPT' if client else 'BUY-IN STOCK SHEET'
    doc_sub = '' if client else '<div style="font-size:10px;color:#c62828;font-weight:bold;margin-top:2px">INTERNAL COPY - not for the seller</div>'
    box_block = ''
    if not client and getattr(buy_order, 'box_number', None):
        box_block = f'<div style="margin-top:6px;display:inline-block;border:2px solid #222;padding:3px 12px;font-size:20px;font-weight:bold">BOX # {buy_order.box_number}</div>'
    total = float(buy_order.total)
    # Actual amount paid (negotiated bundle price), when it differs from the line total.
    actual_rows = ''
    amt = getattr(buy_order, 'amount_paid', None)
    if amt is not None and abs(float(amt) - total) >= 0.005:
        actual = float(amt)
        actual_rows = (f'<tr><td style="padding:4px 8px;font-weight:bold;font-size:13px">AMOUNT ACTUALLY PAID</td>'
                       f'<td style="padding:4px 8px;text-align:right;font-weight:bold;font-size:13px">R {actual:.2f}</td></tr>')
        if not client:
            eff = f'{actual / tot_tcg * 100:.1f}%' if tot_tcg else '-'
            nom = f'{total / tot_tcg * 100:.1f}%' if tot_tcg else '-'
            actual_rows += (f'<tr><td style="padding:3px 8px;color:#555;font-size:11px">Difference vs invoice</td>'
                            f'<td style="padding:3px 8px;text-align:right;font-size:11px">R {total - actual:+.2f}</td></tr>'
                            f'<tr><td style="padding:3px 8px;color:#555;font-size:11px">Rate: invoice / actual</td>'
                            f'<td style="padding:3px 8px;text-align:right;font-size:11px">{nom} / {eff}</td></tr>')
    item_count = buy_order.item_count
    buy_date = buy_order.created_at.strftime('%d-%m-%Y')

    if buy_order.payment_made:
        method_label = METHOD_LABELS.get(buy_order.payment_method, '')
        payment_status = f'{method_label} Paid' if method_label else 'Payment Made'
        payment_color = '#2e7d32'
    else:
        payment_status = 'Payment Pending'
        payment_color = '#e65100'

    seller_note_block = ''
    if buy_order.seller_note:
        note_text = buy_order.seller_note.replace('\n', '<br>')
        seller_note_block = f'''<table style="margin-bottom:14px">
  <tr><td>
    <table style="background:#f9f9f9;border-radius:6px">
      <tr><td style="padding:8px 10px">
        <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Notes</div>
        <div style="font-size:11px;color:#555;line-height:1.3">{note_text}</div>
      </td></tr>
    </table>
  </td></tr>
</table>'''

    controls_html = '''<table width="100%" style="margin-bottom:16px"><tr><td>
      <span class="no-print" style="background:#ff6b35;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;font-weight:bold">
      <a href="javascript:window.print()" style="color:#fff;text-decoration:none">Print</a></span>
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
      <div style="font-size:20px;font-weight:bold;color:#333">{doc_title}</div>{doc_sub}{box_block}
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

{seller_note_block}
<table style="margin-bottom:10px">
  <thead><tr>
    <th width="30">#</th><th>Set</th><th width="60">Card #</th><th>Item</th>
    <th width="55">Variant</th><th width="35">Cond.</th><th width="35" style="text-align:center">Qty</th>
    <th width="65" style="text-align:right">TCG price</th><th width="50" style="text-align:right">{rate_header}</th>
    <th width="65" style="text-align:right">Paid ea.</th>{sell_header}<th width="75" style="text-align:right">Total</th>
  </tr></thead>
  <tbody>{rows}</tbody>{totals_row}
</table>
{legend}

<table style="margin-bottom:14px">
  <tr><td style="width:60%"></td><td style="width:40%">
    <table>
      <tr><td style="padding:3px 8px;color:#555">Items ({item_count})</td><td style="padding:3px 8px;text-align:right">&nbsp;</td></tr>
      <tr><td style="padding:6px 8px;font-weight:bold;font-size:14px;border-top:2px solid #ff6b35">TOTAL PAID</td><td style="padding:6px 8px;text-align:right;font-weight:bold;font-size:14px;border-top:2px solid #ff6b35;color:#ff6b35">R {total:.2f}</td></tr>
      {actual_rows}
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
