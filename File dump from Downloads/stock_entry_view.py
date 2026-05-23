# Add this to products/views.py or create products/stock_views.py

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

from .models import PokemonProduct, CardSet, Era


@staff_member_required
def stock_entry(request):
    """Rapid stock entry — select a set, enter quantities card by card."""
    eras = Era.objects.prefetch_related('cardset_set').order_by('code')
    sets = CardSet.objects.select_related('era').order_by('era__code', 'name')

    selected_set_code = request.GET.get('set', '')
    cards = []

    if selected_set_code:
        cards = list(
            PokemonProduct.objects
            .filter(card_set__code=selected_set_code, is_active=True)
            .select_related('card_set')
            .order_by('card_number', 'variant_override')
            .values('id', 'name', 'card_number', 'variant_override', 'rarity', 'stock', 'price')
        )

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Stock Entry — PokeBulk SA</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Arial, sans-serif; background: #f5f5f5; }}
.header {{ background: #ff6b35; color: #fff; padding: 12px 20px; display: flex; align-items: center; gap: 16px; }}
.header h1 {{ font-size: 18px; }}
.header a {{ color: #fff; text-decoration: none; font-size: 13px; opacity: 0.8; }}
.container {{ max-width: 1100px; margin: 20px auto; padding: 0 16px; }}
.set-picker {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 20px; box-shadow: 0 1px 4px #0001; }}
.set-picker h2 {{ font-size: 15px; margin-bottom: 10px; color: #333; }}
.set-picker select {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }}
.set-picker button {{ margin-top: 10px; background: #ff6b35; color: #fff; border: none; padding: 10px 24px; border-radius: 6px; font-size: 14px; cursor: pointer; width: 100%; }}
.stats {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
.stat {{ background: #fff; border-radius: 8px; padding: 12px 16px; box-shadow: 0 1px 4px #0001; flex: 1; min-width: 120px; }}
.stat .val {{ font-size: 22px; font-weight: 700; color: #ff6b35; }}
.stat .lbl {{ font-size: 11px; color: #888; margin-top: 2px; }}
.save-bar {{ position: sticky; top: 0; z-index: 100; background: #fff; border-bottom: 1px solid #eee; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px #0001; }}
.save-bar .info {{ font-size: 13px; color: #666; }}
.save-btn {{ background: #10B981; color: #fff; border: none; padding: 10px 28px; border-radius: 6px; font-size: 14px; font-weight: 700; cursor: pointer; }}
.save-btn:hover {{ background: #059669; }}
.wipe-btn {{ background: #EF4444; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; font-size: 13px; cursor: pointer; margin-left: 8px; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px #0001; }}
th {{ background: #f8f8f8; text-align: left; padding: 10px 12px; font-size: 12px; color: #666; border-bottom: 1px solid #eee; position: sticky; top: 52px; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: #fafafa; }}
.num {{ font-family: monospace; color: #888; width: 50px; }}
.variant {{ display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; }}
.N  {{ background: #e8e8e8; color: #444; }}
.RH {{ background: #e8e4ff; color: #4c3d99; }}
.H  {{ background: #fff3cd; color: #856404; }}
.qty-input {{ width: 70px; padding: 5px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; text-align: center; }}
.qty-input:focus {{ outline: none; border-color: #ff6b35; box-shadow: 0 0 0 2px #ff6b3520; }}
.qty-input.changed {{ border-color: #10B981; background: #f0fdf4; }}
.price {{ color: #ff6b35; font-weight: 600; }}
.stock-cur {{ color: #888; font-size: 12px; }}
.msg {{ padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }}
.msg.success {{ background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }}
.msg.error {{ background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }}
</style>
</head><body>

<div class="header">
  <div>
    <h1>Stock Entry — PokeBulk SA</h1>
    <a href="/admin/">Back to Admin</a>
  </div>
</div>

<div class="container">

<div class="set-picker">
  <h2>Select a Set to Load Stock</h2>
  <form method="GET">
    <select name="set" onchange="this.form.submit()">
      <option value="">-- Choose a set --</option>"""

    for era in eras:
        era_sets = [s for s in sets if s.era_id == era.id]
        if not era_sets:
            continue
        html += f'\n      <optgroup label="{era.name}">'
        for s in era_sets:
            sel = 'selected' if s.code == selected_set_code else ''
            html += f'\n        <option value="{s.code}" {sel}>[{s.code}] {s.name}</option>'
        html += '\n      </optgroup>'

    html += f"""
    </select>
  </form>
</div>"""

    if cards:
        total = len(cards)
        in_stock = sum(1 for c in cards if c['stock'] > 0)
        total_units = sum(c['stock'] for c in cards)

        selected_set = CardSet.objects.get(code=selected_set_code)

        html += f"""
<div id="msg"></div>

<div class="stats">
  <div class="stat"><div class="val">{total}</div><div class="lbl">Total Cards</div></div>
  <div class="stat"><div class="val">{in_stock}</div><div class="lbl">In Stock</div></div>
  <div class="stat"><div class="val">{total_units}</div><div class="lbl">Total Units</div></div>
  <div class="stat"><div class="val">{selected_set.name}</div><div class="lbl">[{selected_set_code}]</div></div>
</div>

<div class="save-bar">
  <div class="info">Enter quantities — only changed rows will be saved</div>
  <div>
    <button class="wipe-btn" onclick="wipeSet()">Wipe Set to 0</button>
    <button class="save-btn" onclick="saveStock()">Save Stock</button>
  </div>
</div>

<table>
<thead>
  <tr>
    <th width="60">Card #</th>
    <th>Card Name</th>
    <th width="80">Variant</th>
    <th width="100">Rarity</th>
    <th width="80">Price</th>
    <th width="80">Current</th>
    <th width="100">New Qty</th>
  </tr>
</thead>
<tbody>"""

        for card in cards:
            var = card['variant_override'] or 'N'
            var_class = var.replace('-', '')
            price = float(card['price'] or 0)
            html += f"""
  <tr>
    <td class="num">#{str(card['card_number']).zfill(3)}</td>
    <td>{card['name']}</td>
    <td><span class="variant {var_class}">{var}</span></td>
    <td style="font-size:11px;color:#888">{card['rarity'] or ''}</td>
    <td class="price">R {price:.2f}</td>
    <td class="stock-cur">{card['stock']}</td>
    <td><input type="number" class="qty-input" data-id="{card['id']}" 
               data-original="{card['stock']}" min="0" placeholder="-"
               onchange="markChanged(this)" oninput="markChanged(this)"></td>
  </tr>"""

        html += f"""
</tbody>
</table>

<script>
const SET_CODE = "{selected_set_code}";

function markChanged(input) {{
  const orig = parseInt(input.dataset.original) || 0;
  const val = input.value === '' ? null : parseInt(input.value);
  if (val !== null && val !== orig) {{
    input.classList.add('changed');
  }} else {{
    input.classList.remove('changed');
  }}
}}

function showMsg(text, type) {{
  const el = document.getElementById('msg');
  el.innerHTML = '<div class="msg ' + type + '">' + text + '</div>';
  setTimeout(() => el.innerHTML = '', 4000);
}}

function saveStock() {{
  const inputs = document.querySelectorAll('.qty-input.changed');
  if (inputs.length === 0) {{ showMsg('No changes to save.', 'error'); return; }}
  
  const updates = [];
  inputs.forEach(inp => {{
    const qty = inp.value.trim();
    if (qty !== '') {{
      updates.push({{ id: parseInt(inp.dataset.id), stock: parseInt(qty) }});
    }}
  }});

  fetch('/api/stock/update/', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') }},
    body: JSON.stringify({{ updates }})
  }})
  .then(r => r.json())
  .then(data => {{
    if (data.ok) {{
      showMsg('Saved ' + data.updated + ' cards successfully!', 'success');
      inputs.forEach(inp => {{
        inp.dataset.original = inp.value;
        inp.classList.remove('changed');
        // Update current stock display
        inp.closest('tr').querySelector('.stock-cur').textContent = inp.value;
      }});
    }} else {{
      showMsg('Error: ' + data.error, 'error');
    }}
  }});
}}

function wipeSet() {{
  if (!confirm('Set all stock in {selected_set_code} to 0?')) return;
  fetch('/api/stock/wipe/', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') }},
    body: JSON.stringify({{ set_code: SET_CODE }})
  }})
  .then(r => r.json())
  .then(data => {{
    if (data.ok) {{
      showMsg('Wiped ' + data.count + ' cards to 0', 'success');
      document.querySelectorAll('.qty-input').forEach(inp => {{
        inp.value = '';
        inp.dataset.original = '0';
        inp.classList.remove('changed');
        inp.closest('tr').querySelector('.stock-cur').textContent = '0';
      }});
    }}
  }});
}}

function getCookie(name) {{
  const value = '; ' + document.cookie;
  const parts = value.split('; ' + name + '=');
  if (parts.length === 2) return parts.pop().split(';').shift();
  return '';
}}

// Tab key moves to next qty input
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Enter') {{
    const inputs = Array.from(document.querySelectorAll('.qty-input'));
    const idx = inputs.indexOf(document.activeElement);
    if (idx >= 0 && idx < inputs.length - 1) {{
      e.preventDefault();
      inputs[idx + 1].focus();
      inputs[idx + 1].select();
    }}
  }}
}});
</script>"""

    html += """
</div>
</body></html>"""

    return HttpResponse(html, content_type='text/html; charset=utf-8')


@staff_member_required
@require_POST
def stock_update(request):
    """AJAX endpoint to save stock quantities."""
    try:
        data = json.loads(request.body)
        updates = data.get('updates', [])
        if not updates:
            return JsonResponse({'ok': False, 'error': 'No updates provided'})

        ids = [u['id'] for u in updates]
        products = {p.id: p for p in PokemonProduct.objects.filter(id__in=ids)}

        to_update = []
        for u in updates:
            p = products.get(u['id'])
            if p:
                p.stock = max(0, int(u['stock']))
                to_update.append(p)

        with transaction.atomic():
            PokemonProduct.objects.bulk_update(to_update, ['stock'])

        return JsonResponse({'ok': True, 'updated': len(to_update)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


@staff_member_required
@require_POST
def stock_wipe(request):
    """Wipe all stock for a set to 0."""
    try:
        data = json.loads(request.body)
        set_code = data.get('set_code', '')
        if not set_code:
            return JsonResponse({'ok': False, 'error': 'No set code'})
        count = PokemonProduct.objects.filter(card_set__code=set_code).update(stock=0)
        return JsonResponse({'ok': True, 'count': count})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})
