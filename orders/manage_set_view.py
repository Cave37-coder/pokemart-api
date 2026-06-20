from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db import transaction

from .models import PokemonProduct, CardSet

VARIANT_CHOICES = [
    ('N', 'Normal'),
    ('H', 'Holo'),
    ('RH', 'Reverse Holo'),
    ('FE', '1st Edition'),
    ('PB', 'Poke Ball'),
    ('MB', 'Master Ball'),
    ('FB', 'Friend Ball'),
    ('LB', 'Love Ball'),
    ('QB', 'Quick Ball'),
    ('DB', 'Dusk Ball'),
]


@staff_member_required
def manage_set(request, set_code):
    card_set = get_object_or_404(CardSet, code=set_code)
    message = ''

    if request.method == 'POST':
        action = request.POST.get('action')
        selected_ids = [int(i) for i in request.POST.getlist('selected') if i.isdigit()]

        if not selected_ids:
            message = 'No products were selected — nothing changed.'
        else:
            qs = PokemonProduct.objects.filter(id__in=selected_ids, card_set=card_set)

            if action == 'delete':
                deleted_count = qs.count()
                qs.delete()
                message = f'Deleted {deleted_count} product(s).'

            elif action == 'apply_variant':
                new_variant = request.POST.get('variant_value', '').strip()
                if not new_variant:
                    message = 'No variant was chosen — nothing changed.'
                else:
                    updated = 0
                    with transaction.atomic():
                        for p in qs:
                            p.variant_override = new_variant
                            p.pb_id = ''  # forces regeneration with the new variant on save
                            p.save()
                            updated += 1
                    message = f"Applied variant '{new_variant}' to {updated} product(s)."
            else:
                message = 'Unrecognized action — nothing changed.'

    search = request.GET.get('q', '').strip()
    stock_filter = request.GET.get('stock', '')

    products = PokemonProduct.objects.filter(card_set=card_set).order_by(
        'card_number', 'variant_sort', 'name'
    )
    if search:
        products = products.filter(name__icontains=search)
    if stock_filter == 'in':
        products = products.filter(stock__gt=0)
    elif stock_filter == 'out':
        products = products.filter(stock=0)

    products = list(products)

    rows = ''
    for p in products:
        img = p.image_small_url or p.image_url or ''
        if img:
            img_tag = f'<img src="{img}" style="width:36px;height:50px;object-fit:cover;border-radius:4px;background:#222">'
        else:
            img_tag = '<div style="width:36px;height:50px;background:#333;border-radius:4px"></div>'
        stock_color = '#4ade80' if p.stock > 0 else '#f43f5e'
        rows += f'''<tr style="border-bottom:1px solid #2a2a3a">
            <td style="padding:6px 8px"><input type="checkbox" name="selected" value="{p.id}"></td>
            <td style="padding:6px 8px">{img_tag}</td>
            <td style="padding:6px 8px;font-size:12px">{p.card_number if p.card_number is not None else '--'}</td>
            <td style="padding:6px 8px;font-size:12px">{p.name}</td>
            <td style="padding:6px 8px;font-size:12px">{p.get_rarity_display()}</td>
            <td style="padding:6px 8px;font-size:12px;font-weight:bold">{p.variant_override or '-'}</td>
            <td style="padding:6px 8px;font-size:12px;color:#888">{p.variant_sort}</td>
            <td style="padding:6px 8px;font-size:12px;color:{stock_color};font-weight:bold">{p.stock}</td>
            <td style="padding:6px 8px;font-size:12px">R {p.price:.2f}</td>
            <td style="padding:6px 8px;font-size:10px;color:#888">{p.pb_id}</td>
            <td style="padding:6px 8px;font-size:10px;color:#888">{p.id}</td>
        </tr>'''

    variant_options = ''.join(
        f'<option value="{code}">{code} - {label}</option>' for code, label in VARIANT_CHOICES
    )

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Manage {card_set.code} - PokeBulk SA</title>
<style>
* {{ box-sizing:border-box }}
body {{ font-family:Arial,sans-serif;background:#0d0d12;color:#eee;padding:20px;margin:0 }}
table {{ border-collapse:collapse;width:100%;background:#14141c;border-radius:8px;overflow:hidden }}
th {{ background:#1a1a24;font-size:11px;text-align:left;padding:8px;color:#a0a0b0;border-bottom:1px solid #2a2a3a }}
input[type=text] {{ background:#1a1a24;border:1px solid #2a2a3a;color:#fff;padding:6px 10px;border-radius:6px }}
select {{ background:#1a1a24;border:1px solid #2a2a3a;color:#fff;padding:6px 10px;border-radius:6px }}
button {{ background:#ff6b35;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold }}
button.danger {{ background:#dc2626 }}
button.secondary {{ background:#2a2a3a;font-weight:normal }}
.msg {{ background:#1a1a24;border-left:3px solid #ff6b35;padding:10px 14px;border-radius:6px;margin-bottom:16px;font-size:13px }}
</style>
</head><body>
<h1 style="font-size:20px;margin-bottom:4px">Manage Set: {card_set.name} [{card_set.code}]</h1>
<div style="color:#888;font-size:13px;margin-bottom:16px">{len(products)} product(s) shown</div>
{f'<div class="msg">{message}</div>' if message else ''}

<form method="get" style="margin-bottom:16px;display:flex;gap:8px;align-items:center">
  <input type="text" name="q" placeholder="Search card name..." value="{search}">
  <select name="stock" onchange="this.form.submit()">
    <option value="" {"selected" if stock_filter == "" else ""}>All stock</option>
    <option value="in" {"selected" if stock_filter == "in" else ""}>In stock only</option>
    <option value="out" {"selected" if stock_filter == "out" else ""}>Out of stock only</option>
  </select>
  <button type="submit">Filter</button>
</form>

<form method="post" id="bulk-form">
  <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center">
    <button type="button" class="secondary" onclick="document.querySelectorAll('input[name=selected]').forEach(c=>c.checked=true)">Select All</button>
    <button type="button" class="secondary" onclick="document.querySelectorAll('input[name=selected]').forEach(c=>c.checked=false)">Select None</button>
    <select name="variant_value">
      <option value="">-- choose variant --</option>
      {variant_options}
    </select>
    <button type="submit" name="action" value="apply_variant" onclick="return confirm('Apply the selected variant to all checked products?')">Apply Variant</button>
    <button type="submit" name="action" value="delete" class="danger" onclick="return confirm('Permanently delete all checked products? This cannot be undone.')">Delete Selected</button>
  </div>
  <table>
    <thead><tr>
      <th></th><th>Image</th><th>Card #</th><th>Name</th><th>Rarity</th><th>Variant</th><th>Sort</th><th>Stock</th><th>Price</th><th>pb_id</th><th>ID</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</form>
</body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')
