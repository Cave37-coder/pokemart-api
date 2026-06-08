from rest_framework import viewsets, filters
from django.db.models import Case, When, IntegerField, Value
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from .models import PokemonProduct, Category, PokemonType
from .serializers import PokemonProductSerializer, CategorySerializer, PokemonTypeSerializer


class PokemonProductFilter(django_filters.FilterSet):
    era = django_filters.CharFilter(field_name='card_set__era__code', lookup_expr='iexact')
    card_set = django_filters.CharFilter(field_name='card_set__code', lookup_expr='iexact')
    energy_type = django_filters.CharFilter(field_name='pokemon_types__name', lookup_expr='iexact')
    supertype = django_filters.CharFilter(field_name='supertype', lookup_expr='icontains')
    rarity = django_filters.CharFilter(field_name='rarity', lookup_expr='iexact')
    category_slug = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')
    pokedex = django_filters.NumberFilter(field_name='pokedex_number', lookup_expr='exact')
    subtype = django_filters.CharFilter(field_name='card_subtypes', lookup_expr='icontains')
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    in_stock = django_filters.BooleanFilter(field_name='stock', method='filter_in_stock')

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset

    class Meta:
        model = PokemonProduct
        fields = ['era', 'card_set', 'energy_type', 'supertype', 'rarity', 'category', 'min_price', 'max_price', 'in_stock', 'subtype']


class PokemonProductViewSet(viewsets.ModelViewSet):
    queryset = PokemonProduct.objects.filter(is_active=True).select_related(
        'category', 'card_set', 'card_set__era'
    ).prefetch_related('pokemon_types')
    serializer_class = PokemonProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PokemonProductFilter
    search_fields = ['name', 'card_set__name', 'description', 'artist', 'pokedex_number', 'card_number']
    ordering_fields = ['price', 'created_at', 'name', 'card_number', 'pokedex_number']
    ordering = ['-card_set__release_date', 'card_number', 'variant_sort']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]


class PokemonTypeViewSet(viewsets.ModelViewSet):
    queryset = PokemonType.objects.all()
    serializer_class = PokemonTypeSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]


from collections import defaultdict
from datetime import date as date_type
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
import json

from .models import PokemonProduct, CardSet, Era

ERA_ORDER = [
    'MEG', 'SV', 'SWSH', 'SM', 'XY', 'BW', 'HGSS', 'DP', 'EX',
    'WotCO', 'WotCL', 'WotCN', 'WotC', 'OTHER', 'PROMO',
]

ERA_LABELS = {
    'MEG':   'Mega Evolution',
    'SV':    'Scarlet & Violet',
    'SWSH':  'Sword & Shield',
    'SM':    'Sun & Moon',
    'XY':    'XY Era',
    'BW':    'Black & White',
    'HGSS':  'HG&SS',
    'DP':    'D&P / Platinum',
    'EX':    'EX Era',
    'WotCO': 'e-Card',
    'WotCL': 'Legendary',
    'WotCN': 'Neo',
    'WotC':  'WotC Base',
    'OTHER': 'Special / Other',
    'PROMO': 'Promos',
}


@staff_member_required
def stock_entry(request):
    selected_set_code = request.GET.get('set', '')

    all_sets = sorted(
        list(
            CardSet.objects
            .select_related('era')
            .annotate(card_count=Count('products'))
        ),
        key=lambda s: s.release_date if isinstance(s.release_date, date_type) else date_type(1900, 1, 1),
        reverse=True
    )

    cards = []
    if selected_set_code:
        cards = list(
            PokemonProduct.objects
            .filter(card_set__code=selected_set_code, is_active=True)
            .select_related('card_set')
            .order_by('card_number', 'variant_sort')
            .values('id', 'name', 'card_number', 'variant_sort', 'variant_override', 'rarity', 'stock', 'price')
        )
        VALID_VARIANTS = {'N','H','RH','PB','MB','LB','FB','QB','UB','DB','TR','SE','PBP','MBP','CC','TT'}
        for c in cards:
            vs = c.get('variant_override') or ''
            c['var_label'] = vs if vs in VALID_VARIANTS else 'N'

    # Build grouped dropdown
    sets_with_cards = [s for s in all_sets if s.card_count > 0]
    sets_empty      = [s for s in all_sets if s.card_count == 0]

    by_era = defaultdict(list)
    for s in sets_with_cards:
        era = s.era.code if s.era else 'OTHER'
        by_era[era].append(s)

    options_html = '<option value="">-- Choose a set --</option>'

    for era_code in ERA_ORDER:
        era_sets = by_era.get(era_code, [])
        if not era_sets:
            continue
        era_label = ERA_LABELS.get(era_code, era_code)
        options_html += f'<optgroup label="{era_label}">'
        for s in era_sets:
            sel = 'selected' if s.code == selected_set_code else ''
            release = str(s.release_date) if s.release_date else ''
            release_label = f' · {release}' if release else ''
            options_html += f'<option value="{s.code}" {sel}>[{s.code}] {s.name} ({s.card_count}){release_label}</option>'
        options_html += '</optgroup>'

    # Any era not in ERA_ORDER
    other_eras = set(by_era.keys()) - set(ERA_ORDER)
    if other_eras:
        options_html += '<optgroup label="Other">'
        for era_code in sorted(other_eras):
            for s in by_era[era_code]:
                sel = 'selected' if s.code == selected_set_code else ''
                release = str(s.release_date) if s.release_date else ''
                options_html += f'<option value="{s.code}" {sel}>[{s.code}] {s.name} ({s.card_count})</option>'
        options_html += '</optgroup>'

    # Empty sets at bottom
    if sets_empty:
        options_html += '<optgroup label="Empty Sets">'
        for s in sets_empty:
            sel = 'selected' if s.code == selected_set_code else ''
            options_html += f'<option value="{s.code}" {sel}>[{s.code}] {s.name}</option>'
        options_html += '</optgroup>'

    cards_html = ''
    if cards:
        selected_set = next((s for s in all_sets if s.code == selected_set_code), None)
        set_name = selected_set.name if selected_set else selected_set_code
        total = len(cards)
        in_stock = sum(1 for c in cards if c['stock'] > 0)
        total_units = sum(c['stock'] for c in cards)

        VAR_COLORS = {
            'N':   '#e8e8e8;color:#333',
            'H':   '#fff3cd;color:#856404',
            'RH':  '#e8e4ff;color:#4c3d99',
            'PB':  '#d4edda;color:#155724',
            'MB':  '#6f42c1;color:#fff',
            'LB':  '#f8d7da;color:#721c24',
            'FB':  '#cce5ff;color:#004085',
            'QB':  '#fff3cd;color:#856404',
            'UB':  '#d6d8d9;color:#1b1e21',
            'DB':  '#343a40;color:#fff',
            'TR':  '#dc3545;color:#fff',
            'SE':  '#fd7e14;color:#fff',
            'PBP': '#20c997;color:#fff',
            'MBP': '#6610f2;color:#fff',
            'CC':  '#17a2b8;color:#fff',
            'TT':  '#ff6b35;color:#fff',
        }

        rows = ''
        for card in cards:
            var = card.get('var_label') or card.get('variant_override') or 'N'
            var_style = VAR_COLORS.get(var, '#e8e8e8;color:#333')
            price = float(card['price'] or 0)
            card_num = str(card['card_number']).zfill(3) if card['card_number'] is not None else '???'
            rows += f'''<tr style="scroll-margin-top:120px">
              <td style="font-family:monospace;color:#888;font-size:15px;padding:12px 14px">#{card_num}</td>
              <td style="font-size:15px;padding:12px 14px;font-weight:500">{card["name"]}</td>
              <td style="padding:12px 14px"><span style="background:{var_style};padding:4px 12px;border-radius:10px;font-size:14px;font-weight:700">{var}</span></td>
              <td style="font-size:13px;color:#888;padding:12px 14px">{card["rarity"] or ""}</td>
              <td style="color:#ff6b35;font-weight:600;font-size:15px;padding:12px 14px">R {price:.2f}</td>
              <td style="color:#888;font-size:15px;padding:12px 14px">{card["stock"]}</td>
              <td style="padding:12px 14px"><input type="number" class="qty" data-id="{card["id"]}" data-orig="{card["stock"]}"
                         min="0" placeholder="-" style="width:90px;padding:8px;border:1px solid #ddd;border-radius:4px;text-align:center;font-size:16px;font-weight:600"
                         oninput="this.style.borderColor=this.value!==''?'#10B981':'#ddd'"></td>
              <td style="padding:12px 14px"><button onclick="delProd({card['id']},this)" style="background:#dc3545;color:#fff;border:none;border-radius:3px;padding:4px 12px;cursor:pointer;font-size:14px;line-height:1.6">✕</button></td>
            </tr>'''

        cards_html = f'''
<div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap">
  <div style="background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 4px #0001;flex:1">
    <div style="font-size:22px;font-weight:700;color:#ff6b35">{total}</div>
    <div style="font-size:11px;color:#888">Total Cards</div>
  </div>
  <div style="background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 4px #0001;flex:1">
    <div style="font-size:22px;font-weight:700;color:#ff6b35">{in_stock}</div>
    <div style="font-size:11px;color:#888">In Stock</div>
  </div>
  <div style="background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 4px #0001;flex:1">
    <div style="font-size:22px;font-weight:700;color:#ff6b35">{total_units}</div>
    <div style="font-size:11px;color:#888">Total Units</div>
  </div>
  <div style="background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 4px #0001;flex:1">
    <a href="/api/stock/print/?set={selected_set_code}" target="_blank"
       style="display:block;background:#ff6b35;color:#fff;text-align:center;padding:10px;border-radius:6px;font-weight:700;text-decoration:none;font-size:13px">
      Print Count Sheet
    </a>
  </div>
  <div style="background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 4px #0001;flex:2">
    <div style="font-size:20px;font-weight:800;color:#ff6b35">{set_name}</div>
    <div style="font-size:12px;color:#888;margin-top:2px">[{selected_set_code}] · {selected_set_code}</div>
  </div>
</div>

<div id="msg"></div>

<div style="position:sticky;top:0;z-index:100;background:#fff;border-bottom:1px solid #eee;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px #0001;margin-bottom:0">
  <div style="font-size:13px;color:#666">Enter quantities - only changed rows saved</div>
  <div>
    <button onclick="wipeSet()" style="background:#EF4444;color:#fff;border:none;padding:10px 20px;border-radius:6px;font-size:13px;cursor:pointer;margin-right:8px">Wipe to 0</button>
    <button onclick="saveStock()" style="background:#10B981;color:#fff;border:none;padding:10px 28px;border-radius:6px;font-size:14px;font-weight:700;cursor:pointer">Save Stock</button>
  </div>
</div>

<table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px #0001;margin-top:0">
<thead style="position:sticky;top:57px">
  <tr style="background:#f8f8f8">
    <th style="text-align:left;padding:12px 14px;font-size:13px;color:#666;border-bottom:1px solid #eee" width="70">Card #</th>
    <th style="text-align:left;padding:12px 14px;font-size:13px;color:#666;border-bottom:1px solid #eee">Name</th>
    <th style="text-align:left;padding:12px 14px;font-size:13px;color:#666;border-bottom:1px solid #eee" width="90">Variant</th>
    <th style="text-align:left;padding:12px 14px;font-size:13px;color:#666;border-bottom:1px solid #eee" width="120">Rarity</th>
    <th style="text-align:left;padding:12px 14px;font-size:13px;color:#666;border-bottom:1px solid #eee" width="100">Price</th>
    <th style="text-align:left;padding:12px 14px;font-size:13px;color:#666;border-bottom:1px solid #eee" width="90">Current</th>
    <th style="text-align:left;padding:12px 14px;font-size:13px;color:#666;border-bottom:1px solid #eee" width="120">New Qty</th>
    <th width="60"></th>
  </tr>
</thead>
<tbody><tr><td colspan="8" style="height:100px;padding:0"></td></tr>{rows}</tbody>
</table>

<script>
const SET_CODE = "{selected_set_code}";
function delProd(id,btn){{
  if(!confirm('Permanently delete this card from the database?'))return;
  fetch('/api/stock/delete/'+id+'/',{{method:'POST',headers:{{'X-CSRFToken':getCookie('csrftoken')}}}})
  .then(r=>r.json()).then(d=>{{
    if(d.success)btn.closest('tr').remove();
    else alert('Delete failed');
  }});
}}
function getCookie(n){{const v='; '+document.cookie;const p=v.split('; '+n+'=');if(p.length===2)return p.pop().split(';').shift();return'';}}
function showMsg(t,ok){{
  const el=document.getElementById('msg');
  el.innerHTML='<div style="padding:12px;border-radius:6px;margin-bottom:12px;background:'+(ok?'#d1fae5':'#fee2e2')+';color:'+(ok?'#065f46':'#991b1b')+'">'+t+'</div>';
  setTimeout(()=>el.innerHTML='',4000);
}}
function saveStock(){{
  const inputs=[...document.querySelectorAll('.qty')].filter(i=>i.value.trim()!=='');
  if(!inputs.length){{showMsg('No quantities entered',false);return;}}
  const updates=inputs.map(i=>({{id:parseInt(i.dataset.id),stock:parseInt(i.value)}}));
  fetch('/api/stock/update/',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')}},body:JSON.stringify({{updates}})}})
  .then(r=>r.json()).then(d=>{{
    if(d.ok){{showMsg('Saved '+d.updated+' cards!',true);inputs.forEach(i=>{{i.closest('tr').querySelector('td:nth-child(6)').textContent=i.value;i.value='';i.style.borderColor='#ddd';}});}}
    else showMsg('Error: '+d.error,false);
  }});
}}
function wipeSet(){{
  if(!confirm('Wipe all stock in {selected_set_code} to 0?'))return;
  fetch('/api/stock/wipe/',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')}},body:JSON.stringify({{set_code:SET_CODE}})}})
  .then(r=>r.json()).then(d=>{{if(d.ok){{showMsg('Wiped '+d.count+' cards to 0',true);document.querySelectorAll('td:nth-child(6)').forEach(td=>td.textContent='0');}}}});
}}
document.addEventListener('keydown',function(e){{
  if(e.key==='Enter'){{
    const inputs=[...document.querySelectorAll('.qty')];
    const idx=inputs.indexOf(document.activeElement);
    if(idx>=0&&idx<inputs.length-1){{e.preventDefault();inputs[idx+1].focus();inputs[idx+1].select();}}
  }}
}});
</script>'''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Stock Entry - PokeBulk SA</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:Arial,sans-serif;background:#f5f5f5}}
tr:hover td{{background:#fafafa}}td{{padding:12px 14px;border-bottom:1px solid #f0f0f0;font-size:15px}}
select optgroup{{font-weight:700;color:#ff6b35}}
select option{{font-weight:400;color:#333}}</style>
</head><body>
<div style="background:#ff6b35;color:#fff;padding:12px 20px;margin-bottom:20px">
  <h1 style="font-size:18px;display:inline">Stock Entry - PokeBulk SA</h1>
  <a href="/admin/" style="color:#fff;text-decoration:none;font-size:13px;opacity:0.8;margin-left:20px">Back to Admin</a>
</div>
<div style="max-width:1200px;margin:0 auto;padding:0 16px">
  <div style="background:#fff;border-radius:8px;padding:16px;margin-bottom:20px;box-shadow:0 1px 4px #0001">
    <h2 style="font-size:15px;margin-bottom:10px;color:#333">Select a Set</h2>
    <form method="GET">
      <select name="set" onchange="this.form.submit()" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:14px">
        {options_html}
      </select>
    </form>
  </div>
  {cards_html}
</div></body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')


@staff_member_required
def delete_product(request, product_id):
    if request.method == 'POST':
        try:
            p = PokemonProduct.objects.get(id=product_id)
            p.delete()
            return JsonResponse({'success': True})
        except PokemonProduct.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'}, status=404)
    return JsonResponse({'success': False}, status=405)


@staff_member_required
@require_POST
def stock_update(request):
    try:
        data = json.loads(request.body)
        updates = data.get('updates', [])
        products = {p.id: p for p in PokemonProduct.objects.filter(id__in=[u['id'] for u in updates])}
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
    try:
        data = json.loads(request.body)
        set_code = data.get('set_code', '')
        count = PokemonProduct.objects.filter(card_set__code=set_code).update(stock=0)
        return JsonResponse({'ok': True, 'count': count})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


@staff_member_required
def stock_print(request):
    set_code = request.GET.get('set', '')
    if not set_code:
        return HttpResponse('<h2>No set selected. Go back and choose a set first.</h2>')

    try:
        card_set = CardSet.objects.select_related('era').get(code=set_code)
    except CardSet.DoesNotExist:
        return HttpResponse(f'<h2>Set "{set_code}" not found.</h2>')

    cards = list(
        PokemonProduct.objects
        .filter(card_set__code=set_code, is_active=True)
        .order_by('card_number', 'variant_sort')
        .values('id', 'name', 'card_number', 'variant_sort', 'variant_override', 'rarity', 'stock', 'price')
    )
    VALID_VARIANTS = {'N','H','RH','PB','MB','LB','FB','QB','UB','DB','TR','SE','PBP','MBP','CC','TT'}
    for c in cards:
        vs = c.get('variant_override') or ''
        c['var_label'] = vs if vs in VALID_VARIANTS else 'N'

    VARIANT_LABEL = {
        'N': 'Normal', 'H': 'Holo', 'RH': 'Rev Holo',
        'PB': 'Poke Ball', 'MB': 'Master Ball', 'LB': 'Love Ball',
        'FB': 'Friend Ball', 'QB': 'Quick Ball', 'UB': 'Ultra Ball',
        'DB': 'Dusk Ball', 'TR': 'Team Rocket', 'SE': 'Secret',
        'PBP': 'PB Pattern', 'MBP': 'MB Pattern',
        'CC': 'Code Card', 'TT': 'Trick or Trade',
    }

    from itertools import groupby as igroup
    grouped = []
    for num, grp in igroup(cards, key=lambda c: c['card_number']):
        variants = list(grp)
        grouped.append(variants)

    total_groups = len(grouped)
    col_size = -(-total_groups // 3)
    cols = [grouped[0:col_size], grouped[col_size:col_size*2], grouped[col_size*2:]]

    def render_group(variants):
        if variants is None:
            return '<td colspan="6" style="border-bottom:2px solid #eee"></td>'
        rows = ''
        for vi, card in enumerate(variants):
            var = card.get('var_label') or card.get('variant_override') or 'N'
            var_label = VARIANT_LABEL.get(var, var)
            num_str = str(card['card_number'] or '').zfill(3)
            name = card['name'] if vi == 0 else ''
            num_cell = f'<td class="num">{num_str}</td>' if vi == 0 else '<td class="num"></td>'
            name_cell = f'<td class="name">{name}</td>' if vi == 0 else f'<td class="name" style="color:#888;font-size:7px;padding-left:8px">{var_label}</td>'
            border = 'border-bottom:1px solid #eee;' if vi < len(variants)-1 else 'border-bottom:2px solid #ccc;'
            rows += f'<tr style="{border}">{num_cell}{name_cell}<td class="var">{var}</td><td class="box"></td><td class="box"></td><td class="box"></td></tr>'
        return rows

    max_rows = col_size
    rows_html = ''
    for i in range(max_rows):
        g1 = cols[0][i] if i < len(cols[0]) else None
        g2 = cols[1][i] if i < len(cols[1]) else None
        g3 = cols[2][i] if i < len(cols[2]) else None

        r1 = list(render_group(g1).split('</tr>') if g1 else [''])
        r2 = list(render_group(g2).split('</tr>') if g2 else [''])
        r3 = list(render_group(g3).split('</tr>') if g3 else [''])
        r1 = [r for r in r1 if r.strip()]
        r2 = [r for r in r2 if r.strip()]
        r3 = [r for r in r3 if r.strip()]
        max_v = max(len(r1), len(r2), len(r3), 1)

        bg = '#ffffff' if i % 2 == 0 else '#f9f9f9'
        for vi in range(max_v):
            c1 = (r1[vi] + '</tr>') if vi < len(r1) else '<tr><td colspan="6"></td></tr>'
            c2 = (r2[vi] + '</tr>') if vi < len(r2) else '<tr><td colspan="6"></td></tr>'
            c3 = (r3[vi] + '</tr>') if vi < len(r3) else '<tr><td colspan="6"></td></tr>'
            def inner(r):
                import re
                tds = re.findall(r'<td[^>]*>.*?</td>', r, re.DOTALL)
                return ''.join(tds)
            rows_html += f'<tr style="background:{bg}">{inner(c1)}<td class="div"></td>{inner(c2)}<td class="div"></td>{inner(c3)}</tr>\n'

    set_name = card_set.name
    era_name = card_set.era.name if card_set.era else ''
    release = str(card_set.release_date) if card_set.release_date else ''
    total_cards = len(cards)

    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Stock Count - {set_name}</title>
<style>
  @page {{ size: A4 landscape; margin: 8mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; font-size: 8px; color: #111; }}
  .header {{ display: flex; justify-content: space-between; align-items: center;
             border-bottom: 2px solid #ff6b35; padding-bottom: 5px; margin-bottom: 6px; }}
  .header h1 {{ font-size: 13px; color: #ff6b35; font-weight: 800; }}
  .header h2 {{ font-size: 10px; color: #333; }}
  .header-right {{ display: flex; gap: 16px; align-items: center; font-size: 8px; color: #666; }}
  .field {{ display: flex; flex-direction: column; gap: 2px; }}
  .field label {{ font-size: 7px; color: #999; text-transform: uppercase; }}
  .field .line {{ border-bottom: 1px solid #999; width: 100px; height: 14px; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  thead th {{ background: #ff6b35; color: #fff; padding: 3px 4px;
              text-align: left; font-size: 7px; font-weight: 700; text-transform: uppercase; }}
  td {{ padding: 2px 3px; border-bottom: 1px solid #eee; vertical-align: middle; overflow: hidden; white-space: nowrap; }}
  td.num  {{ width: 26px; font-family: monospace; color: #888; font-size: 7px; }}
  td.name {{ font-weight: 600; font-size: 8px; overflow: hidden; text-overflow: ellipsis; }}
  td.var  {{ width: 18px; font-size: 7px; font-weight: 700; color: #ff6b35; text-align:center; }}
  td.box  {{ width: 36px; }}
  td.box::after {{ content:""; display:block; border:1px solid #aaa; border-radius:2px; height:18px; width:32px; margin:0 auto; }}
  td.div  {{ width: 6px; background: #f0f0f0; }}
  .footer {{ margin-top: 6px; border-top: 1px solid #ddd; padding-top: 4px;
             display: flex; justify-content: space-between; font-size: 7px; color: #aaa; }}
  .page-header {{ display: none; }}
  @media print {{
    .no-print {{ display: none !important; }}
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .page-header {{ display: block; position: running(header); font-size: 9px; color: #ff6b35; font-weight: 700; text-align: right; }}
    @page {{ @top-right {{ content: element(header); }} }}
  }}
</style>
</head>
<body>
<div class="page-header">{set_name} · {set_code}</div>

<div class="no-print" style="background:#ff6b35;color:#fff;padding:8px 14px;margin-bottom:10px;display:flex;gap:12px;align-items:center">
  <strong>PokeBulk Stock Count - {set_name}</strong>
  <button onclick="window.print()" style="background:#fff;color:#ff6b35;border:none;padding:5px 14px;border-radius:4px;font-weight:700;cursor:pointer">Print</button>
  <a href="/api/stock/entry/?set={set_code}" style="color:#fff;font-size:12px">Back</a>
</div>

<div class="header">
  <div>
    <h1 style="font-size:16px;color:#ff6b35;font-weight:800">{set_name}</h1>
    <h2>PokeBulk SA Stock Count · {era_name} · {set_code} · {release} · {total_cards} variants</h2>
  </div>
  <div class="header-right">
    <div class="field"><label>Date</label><div class="line" style="width:80px"></div></div>
    <div class="field"><label>Counted By</label><div class="line" style="width:110px"></div></div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th style="width:24px">#</th><th>Card Name</th><th style="width:16px">V</th>
      <th style="width:34px">1</th><th style="width:34px">2</th><th style="width:34px">3</th>
      <th style="width:5px"></th>
      <th style="width:24px">#</th><th>Card Name</th><th style="width:16px">V</th>
      <th style="width:34px">1</th><th style="width:34px">2</th><th style="width:34px">3</th>
      <th style="width:5px"></th>
      <th style="width:24px">#</th><th>Card Name</th><th style="width:16px">V</th>
      <th style="width:34px">1</th><th style="width:34px">2</th><th style="width:34px">3</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>

<div class="footer">
  <span>PokeBulk SA · 4 Heloise Street, Birchleigh North · enquiries@pokebulk.co.za</span>
  <span>Printed: <span id="now"></span></span>
</div>
<script>document.getElementById('now').textContent = new Date().toLocaleString('en-ZA');</script>
</body>
</html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')


def sets_list(request):
    sets = CardSet.objects.select_related('era').annotate(
        pc=Count('products')
    ).filter(pc__gt=0).order_by('-release_date', 'name')
    data = []
    for s in sets:
        data.append({
            'code': s.code,
            'name': s.name,
            'symbol_url': s.symbol_url or '',
            'logo_url': s.logo_url or '',
            'release_date': str(s.release_date) if s.release_date else '',
            'era_code': s.era.code if s.era else '',
            'era_name': s.era.name if s.era else '',
            'regulation_mark': s.regulation_mark or '',
        })
    return JsonResponse({'results': data})


@csrf_exempt
@staff_member_required
def bundle_stock_entry(request):
    bundles = list(
        PokemonProduct.objects
        .filter(category__slug='bundles')
        .select_related('card_set', 'card_set__era')
        .order_by('card_set__release_date', 'card_set__name')
        .exclude(card_set__release_date__isnull=True)
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
            .order_by('card_set__release_date', 'card_set__name')
            .exclude(card_set__release_date__isnull=True)
            .values('id', 'name', 'card_set__name', 'card_set__code', 'card_set__era__name',
                    'card_set__logo_url', 'card_set__symbol_url', 'stock', 'price', 'is_active')
        )
        saved_msg = f'<div style="background:#d4edda;color:#155724;padding:10px 16px;border-radius:6px;margin-bottom:16px;font-weight:600">Saved {updated} bundles successfully!</div>'

    rows = ''
    for b in bundles:
        logo = b['card_set__logo_url'] or b['card_set__symbol_url'] or ''
        logo_html = f'<img src="{logo}" style="height:28px;max-width:60px;object-fit:contain;vertical-align:middle;margin-right:8px">' if logo else ''
        era = b['card_set__era__name'] or ''
        set_name = b['card_set__name'] or b['name']
        active_checked = 'checked' if b['is_active'] else ''
        price = float(b['price'] or 0)
        stock = b['stock'] or 0
        row_bg = '#f8fff8' if b['is_active'] else '#ffffff'
        rows += f'''<tr style="background:{row_bg};border-bottom:1px solid #eee">
            <td style="padding:8px 10px;font-size:12px;color:#888">{era}</td>
            <td style="padding:8px 10px;font-size:13px">{logo_html}<strong>{set_name}</strong></td>
            <td style="padding:8px 10px"><input type="number" name="price_{b['id']}" value="{price:.2f}" step="0.01" min="0" style="width:90px;padding:5px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px"></td>
            <td style="padding:8px 10px"><input type="number" name="stock_{b['id']}" value="{stock}" min="0" style="width:70px;padding:5px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px"></td>
            <td style="padding:8px 10px;text-align:center"><input type="checkbox" name="active_{b['id']}" {active_checked} style="width:18px;height:18px;cursor:pointer"></td>
        </tr>'''

    active_count = sum(1 for b in bundles if b['is_active'])
    total = len(bundles)

    html = f'''<!DOCTYPE html>
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
<a href="/api/stock/entry/" class="back">&laquo; Back to Card Stock Entry</a>
<h1>Complete Set Bundle Stock</h1>
<div class="stats">{total} bundles total &middot; {active_count} active on site</div>
{saved_msg}
<form method="post">
<table>
<thead><tr>
  <th style="width:120px">Era</th>
  <th>Set Name</th>
  <th style="width:110px">Price (R)</th>
  <th style="width:90px">Stock</th>
  <th style="width:70px;text-align:center">Active</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
<div style="margin-top:16px;display:flex;gap:12px;align-items:center">
  <button type="submit" class="btn">Save all bundles</button>
  <span style="font-size:12px;color:#888">Tick Active to make bundle visible on site</span>
</div>
</form>
</div></body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')




