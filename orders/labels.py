"""
labels.py -- 40 x 30 mm thermal label images for the Volkano LabelPro Duo (203 dpi => 320 x 240 px).

Michael, 2026-10-28: bought a Volkano LabelPro Duo; prints from the Labelnize app's "Image Printing"
(drag the PNG in, pick the 40x30 paper). Pure black & white (1-bit) so the thermal head prints it crisp.

  order_label_png(order)    -> parcel tag: logo, order #, QR, customer, cell, area, PUDO/COURIER/COLLECTION
  bulk_label_png(buy_order) -> bulk bundle tag: logo, BULK-#, QR, seller, bundle counts

Assets live in orders/assets/ (label_logo.png = 1-bit logo, DejaVuSans-Bold.ttf so the text looks the
same on Railway as locally -- no reliance on system fonts).
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 320, 240          # 40 x 30 mm at 203 dpi
SITE = "https://pokebulk.co.za"
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def _font(size):
    return ImageFont.truetype(os.path.join(_ASSETS, "DejaVuSans-Bold.ttf"), size)


def _fit(draw, text, max_w, start, minimum=12):
    """Largest bold font (start..minimum) that fits max_w; truncates with '…' as a last resort."""
    size = start
    while size >= minimum:
        f = _font(size)
        if draw.textlength(text, font=f) <= max_w:
            return text, f
        size -= 1
    f = _font(minimum)
    while len(text) > 1 and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…", f


def _qr(data, size):
    import segno
    m = segno.make(data, error="m", boost_error=False).matrix
    n = len(m)
    mod = max(1, size // (n + 2))  # +2 = 1-module quiet zone each side
    dim = mod * (n + 2)
    img = Image.new("1", (dim, dim), 1)
    px = img.load()
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                for dy in range(mod):
                    for dx in range(mod):
                        px[(x + 1) * mod + dx, (y + 1) * mod + dy] = 0
    return img


def _base(code_text, qr_data):
    """Common top band: logo (left), code (middle), QR (right)."""
    im = Image.new("1", (W, H), 1)
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(_ASSETS, "label_logo.png")).convert("L")
    logo.thumbnail((116, 116), Image.LANCZOS)
    im.paste(logo.point(lambda v: 255 if v > 128 else 0).convert("1"), (2, 2))
    qr = _qr(qr_data, 104)
    im.paste(qr, (W - qr.width - 2, 2))
    text, f = _fit(d, code_text, W - 120 - qr.width - 6, 34, 16)
    d.text((122, 2 + (qr.height - f.size) // 2 - 4), text, font=f, fill=0)
    return im, d


BAR_H = 34                 # black strip along the bottom
BAR_TOP = H - BAR_H
TEXT_TOP = 122             # just under the logo/QR band
TEXT_BOTTOM = BAR_TOP - 8  # always leave a clear gap above the strip


def _stack(d, lines, top=TEXT_TOP, bottom=TEXT_BOTTOM, gap=4):
    """Draw text lines [(text, start_size)] top-down, shrinking them all together until the block
    fits between `top` and `bottom` (so nothing can run into the bottom strip)."""
    scale = 1.0
    while True:
        laid = []
        y = top
        for text, size in lines:
            t, f = _fit(d, text, W - 10, max(12, int(size * scale)), 11)
            l, tp, r, bt = d.textbbox((0, 0), t, font=f)
            laid.append((t, f, y - tp))
            y += (bt - tp) + gap
        if y - gap <= bottom or scale < 0.5:
            break
        scale -= 0.05
    for t, f, yy in laid:
        d.text((6, yy), t, font=f, fill=0)


def _bar(d, text):
    d.rectangle((0, BAR_TOP, W, H), fill=0)
    t, f = _fit(d, text, W - 12, 26, 14)
    l, tp, r, bt = d.textbbox((0, 0), t, font=f)
    d.text(((W - (r - l)) // 2 - l, BAR_TOP + (BAR_H - (bt - tp)) // 2 - tp), t, font=f, fill=1)


def thankyou_label_png(name, portrait=False):
    """14 x 40 mm 'Thank you' sticker: small logo, THANK YOU!, customer's name (wraps to 2 lines)."""
    w, h = 320, 112
    im = Image.new("1", (w, h), 1)
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(_ASSETS, "label_logo.png")).convert("L")
    logo.thumbnail((100, 100), Image.LANCZOS)
    im.paste(logo.point(lambda v: 255 if v > 128 else 0).convert("1"), (4, (h - logo.height) // 2))
    x, maxw = 114, w - 114 - 4
    t, f = _fit(d, "THANK YOU!", maxw, 38, 16)
    d.text((x, 6), t, font=f, fill=0)
    name = (name or "").strip()
    if name:
        t, f = _fit(d, name, maxw, 26, 20)
        if d.textlength(t, font=f) > maxw or t.endswith("…"):
            # long name: split on the last space into two lines
            first, _, last = name.rpartition(" ")
            lines = [first, last] if first else [name]
            for i, ln in enumerate(lines):
                t2, f2 = _fit(d, ln, maxw, 20, 12)
                d.text((x, 54 + i * 24), t2, font=f2, fill=0)
        else:
            d.text((x, 58), t, font=f, fill=0)
    if portrait:
        im = im.rotate(90, expand=True)
    return _png(im)


def _png(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG", dpi=(203, 203))
    return buf.getvalue()


def order_delivery_word(order):
    sm = (order.shipping_method or "").lower()
    dm = (order.delivery_method or "").lower()
    if sm == "collection" or dm == "collection":
        return "COLLECTION"
    if sm.startswith("pudo"):
        return "PUDO"
    return "COURIER"


def order_area(order):
    parts = [(getattr(order, "delivery_city", "") or "").strip(), (getattr(order, "pudo_locker_name", "") or "").strip()]
    parts = [p for p in parts if p]
    return " - ".join(parts)


def order_label_png(order):
    user = order.user
    name = (f"{user.first_name} {user.last_name}".strip() or user.username)
    phone = getattr(user, "phone_number", "") or ""
    word = order_delivery_word(order)
    area = order_area(order) or ("Collection" if word == "COLLECTION" else "")

    im, d = _base(f"#{order.id}", f"{SITE}/orders/{order.id}")
    lines = [(name, 26), (f"Cell: {phone}" if phone else "Cell: —", 24)]
    if area:
        lines.append((area, 20))
    _stack(d, lines)
    _bar(d, word)
    return _png(im)


_BUNDLE_WORD = {"common": "Commons", "holo": "Holos", "reverse": "Rev Holos"}


def bulk_label_png(buy):
    totals = {}
    for it in buy.items.all():
        if it.bundle_type:
            totals[it.bundle_type] = totals.get(it.bundle_type, 0) + it.quantity
    im, d = _base(buy.buy_number, f"{SITE}/staff/orders?bulk={buy.buy_number}")
    short = {"common": "Com", "holo": "Holo", "reverse": "Rev"}
    parts = [f"{totals[k]} {short[k]}" for k in ("common", "holo", "reverse") if k in totals]
    lines = [(buy.seller_name or "—", 26)]
    if parts:
        lines += [("  ".join(parts), 24), (f"= {sum(totals.values())} cards", 26)]
    _stack(d, lines)
    _bar(d, f"BULK  {buy.created_at.strftime('%d %b %Y')}")
    return _png(im)


def manual_label_png(inv):
    """Parcel tag for a manual invoice. No structured delivery fields -- the delivery word comes from
    the free-text delivery_note ('collection' / 'pudo ...') and the shipping cost."""
    note = (inv.delivery_note or "").strip()
    low = note.lower()
    if "collect" in low:
        word = "COLLECTION"
    elif "pudo" in low or (inv.shipping_cost or 0) > 0:
        word = "PUDO"
    else:
        word = "COLLECTION"
    phone = (inv.customer_phone or "").strip()
    area = " ".join(note.split())[:60] if note and word != "COLLECTION" else ("Collection" if word == "COLLECTION" else "")
    im, d = _base(inv.invoice_number, f"{SITE}/staff/orders?invoice={inv.invoice_number}")
    lines = [(inv.customer_name or "—", 26), (f"Cell: {phone}" if phone else "Cell: —", 24)]
    if area:
        lines.append((area, 20))
    _stack(d, lines)
    _bar(d, word)
    return _png(im)


def box_label_png(buy, index=1, total=1):
    """Stock-box label for a buy-in: BUY-#, big BOX #, seller, and 'k of n' when several boxes."""
    im, d = _base(buy.buy_number, f"{SITE}/staff/orders?buy={buy.buy_number}")
    lines = []
    if buy.box_number:
        lines.append((f"BOX {buy.box_number}", 44))
    lines.append((buy.seller_name or "—", 24))
    _stack(d, lines)
    _bar(d, f"{index} of {total}" if total > 1 else buy.created_at.strftime("%d %b %Y"))
    return _png(im)
