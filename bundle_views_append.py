# Read current views.py
with open('products/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'def bundle_stock_entry' in content:
    print("Already exists")
else:
    bundle_code = '''

@staff_member_required
def bundle_stock_entry(request):
    from django.db.models import Count as DCount
    bundles = list(
        PokemonProduct.objects
        .filter(category__slug='bundles')
        .select_related('card_set', 'card_set__era')
        .order_by('-card_set__release_date', 'card_set__name')
        .values('id', 'name', 'card_set__name', 'card_set__code', 'card_set__era__name',
                'card_set__logo_url', 'card_set__symbol_url', 'stock', 'price', 'is_active')
    )

    saved_msg = ''
    if request.method == 'POST':
        updated = 0
        for b in bundles:
            bid = str(b['id'])
            new_stock = request.POST.get('stock_' + bid)
            new_price = request.POST.get('price_' + bid)
            new_active = request.POST.get('active_' + bid) == 'on'
            if new_stock is not None:
                try:
                    PokemonProduct.objects.filter(id=b['id']).update(
                        stock=int(new_stock),
                        price=float(new_price) if new_price else 0,
                        is_active=new_active,
                    )
                    updated += 1
                except Exception:
                    pass
        bundles = list(
            PokemonProduct.objects
            .filter(category__slug='bundles')
            .select_related('card_set', 'card_set__era')
            .order_by('-card_set__release_date', 'card_set__name')
            .values('id', 'name', 'card_set__name', 'card_set__code', 'card_set__era__name',
                    'card_set__logo_url', 'card_set__symbol_url', 'stock', 'price', 'is_active')
        )
        saved_msg = f\'\'\'<div style="background:#d4edda;color:#155724;padding:10px 16px;border-radius:6px;margin-bottom:16px;font-weight:600">Saved {updated} bundles successfully!</div>\'\'\'

    rows = ''
    for b in bundles:
        logo = b['card_set__logo_url'] or b['card_set__symbol_url'] or ''
        logo_html = f\'\'\'<img src="{logo}" style="height:28px;max-width:60px;object-fit:contain;vertical-align:middle;margin-right:8px">\'\'\' if logo else ''
        era = b['card_set__era__name'] or ''
        set_name = b['card_set__name'] or b['name']
        active_checked = 'checked' if b['is_active'] else ''
        price = float(b['price'] or 0)
        stock = b['stock'] or 0
        row_bg = '#f8fff8' if b['is_active'] else '#ffffff'
        rows += f\'\'\'<tr style="background:{row_bg};border-bottom:1px solid #eee">
            <td style="padding:8px 10px;font-size:12px;color:#888">{era}</td>
            <td style="padding:8px 10px;font-size:13px">{logo_html}<strong>{set_name}</strong></td>
            <td style="padding:8px 10px"><input type="number" name="price_{b[\'id\']}" value="{price:.2f}" step="0.01" min="0" style="width:90px;padding:5px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px"></td>
            <td style="padding:8px 10px"><input type="number" name="stock_{b[\'id\']}" value="{stock}" min="0" style="width:70px;padding:5px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px"></td>
            <td style="padding:8px 10px;text-align:center"><input type="checkbox" name="active_{b[\'id\']}" {active_checked} style="width:18px;height:18px;cursor:pointer"></td>
        </tr>\'\'\'

    active_count = sum(1 for b in bundles if b['is_active'])
    total = len(bundles)

    html = f\'\'\'<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Bundle Stock - PokeBulk SA</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px}}
.wrap{{max-width:900px;margin:0 auto;background:white;border-radius:8px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
h1{{color:#ff6b35;font-size:22px;margin:0 0 6px}}
.stats{{color:#666;font-size:13px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse}}
th{{background:#ff6b35;color:white;padding:10px;text-align:left;font-size:12px}}
tr:hover{{background:#fff8f5!important}}
.btn{{background:#ff6b35;color:white;border:none;padding:10px 24px;border-radius:6px;font-size:14px;font-weight:bold;cursor:pointer}}
.back{{color:#ff6b35;text-decoration:none;font-size:13px;display:inline-block;margin-bottom:16px}}
</style></head><body>
<div class="wrap">
<a href="/stock/entry/" class="back">&laquo; Back to Card Stock Entry</a>
<h1>Complete Set Bundle Stock</h1>
<div class="stats">{total} bundles total &middot; {active_count} active on site</div>
{saved_msg}
<form method="post">
<table>
<thead><tr><th style="width:120px">Era</th><th>Set Name</th><th style="width:110px">Price (R)</th><th style="width:90px">Stock</th><th style="width:70px;text-align:center">Active</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<div style="margin-top:16px;display:flex;gap:12px;align-items:center">
<button type="submit" class="btn">Save all bundles</button>
<span style="font-size:12px;color:#888">Tick Active to make bundle visible on site</span>
</div></form></div></body></html>\'\'\'
    return HttpResponse(html, content_type='text/html; charset=utf-8')
'''
    content = content + bundle_code
    with open('products/views.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done - bundle_stock_entry added")
