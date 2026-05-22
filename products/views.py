from rest_framework import viewsets, filters
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
    search_fields = ['name', 'card_set__name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'card_number', 'pokedex_number']
    ordering = ['-card_set__release_date', 'card_number']

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





# Add this to products/views.py or create products/stock_views.py

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

from .models import PokemonProduct, CardSet, Era



from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Count, Case, When, IntegerField
import json

from .models import PokemonProduct, CardSet


@staff_member_required
def stock_entry(request):
    selected_set_code = request.GET.get('set', '')

    # Sets with cards first (newest first), then empty sets
    all_sets = list(
        CardSet.objects
        .select_related('era')
        .annotate(card_count=Count('products'))
        .order_by('-release_date', 'name')
    )
    sets_with_cards = [s for s in all_sets if s.card_count > 0]
    sets_empty      = sorted([s for s in all_sets if s.card_count == 0], key=lambda s: s.release_date or '1900-01-01', reverse=True)

    cards = []
    if selected_set_code:
        cards = list(
            PokemonProduct.objects
            .filter(card_set__code=selected_set_code, is_active=True)
            .select_related('card_set')
            .order_by('card_number')
            .values('id', 'name', 'card_number', 'variant_override', 'rarity', 'stock', 'price')
        )
        VORDER = {'N': 0, 'RH': 1, 'H': 2}
        cards = sorted(cards, key=lambda c: (c['card_number'], VORDER.get(c['variant_override'] or 'N', 9)))

    # Build dropdown options
    options_html = '<option value="">-- Choose a set --</option>'
    options_html += '<optgroup label="--- Sets with cards ---">'
    for s in sets_with_cards:
        sel = 'selected' if s.code == selected_set_code else ''
        options_html += f'<option value="{s.code}" {sel}>[{s.code}] {s.name} ({s.card_count})</option>'
    options_html += '</optgroup>'
    options_html += '<optgroup label="--- Empty sets ---">'
    for s in sets_empty:
        sel = 'selected' if s.code == selected_set_code else ''
        options_html += f'<option value="{s.code}" {sel}>[{s.code}] {s.name}</option>'
    options_html += '</optgroup>'

    # Build cards table
    cards_html = ''
    if cards:
        selected_set = next((s for s in all_sets if s.code == selected_set_code), None)
        set_name = selected_set.name if selected_set else selected_set_code
        total = len(cards)
        in_stock = sum(1 for c in cards if c['stock'] > 0)
        total_units = sum(c['stock'] for c in cards)

        VAR_COLORS = {
            'N': '#e8e8e8;color:#333',
            'RH': '#e8e4ff;color:#4c3d99',
            'H': '#fff3cd;color:#856404',
        }

        rows = ''
        for card in cards:
            var = card['variant_override'] or 'N'
            var_style = VAR_COLORS.get(var, '#e8e8e8;color:#333')
            price = float(card['price'] or 0)
            rows += f'''<tr style="scroll-margin-top:120px">
              <td style="font-family:monospace;color:#888">#{str(card["card_number"]).zfill(3)}</td>
              <td>{card["name"]}</td>
              <td><span style="background:{var_style};padding:1px 8px;border-radius:10px;font-size:11px;font-weight:700">{var}</span></td>
              <td style="font-size:11px;color:#888">{card["rarity"] or ""}</td>
              <td style="color:#ff6b35;font-weight:600">R {price:.2f}</td>
              <td style="color:#888">{card["stock"]}</td>
              <td><input type="number" class="qty" data-id="{card["id"]}" data-orig="{card["stock"]}"
                         min="0" placeholder="-" style="width:70px;padding:5px;border:1px solid #ddd;border-radius:4px;text-align:center;font-size:14px"
                         oninput="this.style.borderColor=this.value!==''?'#10B981':'#ddd'"></td>
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
  <div style="background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 4px #0001;flex:2">
    <div style="font-size:16px;font-weight:700;color:#ff6b35">{set_name}</div>
    <div style="font-size:11px;color:#888">[{selected_set_code}]</div>
  </div>
</div>

<div id="msg"></div>

<div style="position:sticky;top:0;z-index:100;background:#fff;border-bottom:1px solid #eee;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px #0001;margin-bottom:0">
  <div style="font-size:13px;color:#666">Enter quantities — only changed rows saved</div>
  <div>
    <button onclick="wipeSet()" style="background:#EF4444;color:#fff;border:none;padding:10px 20px;border-radius:6px;font-size:13px;cursor:pointer;margin-right:8px">Wipe to 0</button>
    <button onclick="saveStock()" style="background:#10B981;color:#fff;border:none;padding:10px 28px;border-radius:6px;font-size:14px;font-weight:700;cursor:pointer">Save Stock</button>
  </div>
</div>

<table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px #0001;margin-top:0">
<thead style="position:sticky;top:57px">
  <tr style="background:#f8f8f8">
    <th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee" width="60">Card #</th>
    <th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee">Name</th>
    <th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee" width="80">Variant</th>
    <th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee" width="100">Rarity</th>
    <th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee" width="90">Price</th>
    <th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee" width="80">Current</th>
    <th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee" width="100">New Qty</th>
  </tr>
</thead>
<tbody><tr><td colspan="7" style="height:100px;padding:0"></td></tr>{rows}</tbody>
</table>

<script>
const SET_CODE = "{selected_set_code}";
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
tr:hover td{{background:#fafafa}}td{{padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}}</style>
</head><body>
<div style="background:#ff6b35;color:#fff;padding:12px 20px;margin-bottom:20px">
  <h1 style="font-size:18px;display:inline">Stock Entry — PokeBulk SA</h1>
  <a href="/admin/" style="color:#fff;text-decoration:none;font-size:13px;opacity:0.8;margin-left:20px">Back to Admin</a>
</div>
<div style="max-width:1100px;margin:0 auto;padding:0 16px">
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
