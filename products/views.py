from rest_framework import viewsets, filters
from django.db.models import Case, When, IntegerField, Value, Q
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
    legal_standard = django_filters.BooleanFilter(field_name='legal_standard', method='filter_legal_standard')
    legality = django_filters.CharFilter(method='filter_legality')

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset

    def filter_legal_standard(self, queryset, name, value):
        if value:
            return queryset.filter(legal_standard=True)
        return queryset

    def filter_legality(self, queryset, name, value):
        # Drives the Browse Cards dropdown: All formats / Standard 2026
        # (H/I/J) / Expanded / Rotated -- SV era (G) / Rotated -- SwSh era
        # (F). rotated_g/rotated_f filter on the ACTUAL mark value (per-card
        # regulation_mark, falling back to card_set.regulation_mark when
        # blank) rather than a legal/illegal boolean -- useful as a standalone
        # "show me G-marked stock" filter for clearance, distinct from
        # legal_standard.
        if value == 'standard':
            return queryset.filter(legal_standard=True)
        elif value == 'expanded':
            return queryset.filter(legal_expanded=True)
        elif value == 'rotated_g':
            return queryset.filter(
                Q(regulation_mark='G') | (Q(regulation_mark='') & Q(card_set__regulation_mark='G'))
            )
        elif value == 'rotated_f':
            return queryset.filter(
                Q(regulation_mark='F') | (Q(regulation_mark='') & Q(card_set__regulation_mark='F'))
            )
        return queryset

    class Meta:
        model = PokemonProduct
        fields = ['era', 'card_set', 'energy_type', 'supertype', 'rarity', 'category', 'min_price', 'max_price', 'in_stock', 'subtype', 'legal_standard', 'legality']


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
from django.shortcuts import get_object_or_404
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
            .values('id', 'name', 'card_number', 'variant_sort', 'variant_override', 'rarity', 'stock', 'price', 'condition', 'tcgcsv_product_id')
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
              <td style="padding:12px 14px;white-space:nowrap">
                <button onclick="delProd({card['id']},this)" style="background:#dc3545;color:#fff;border:none;border-radius:3px;padding:4px 10px;cursor:pointer;font-size:14px;line-height:1.6">✕</button>
                <button onclick="addPlayed({card['id']},{card['tcgcsv_product_id'] or 'null'},{card['price']},this)" style="background:#f59e0b;color:#fff;border:none;border-radius:3px;padding:4px 10px;cursor:pointer;font-size:11px;line-height:1.6;margin-left:4px">+Played</button>
              </td>
            </tr>
            <tr id="played-row-{card['id']}" style="display:none;background:#fffbeb">
              <td colspan="2" style="padding:6px 14px;font-size:12px;color:#92400e">↳ Add played copy of <strong>{card["name"]}</strong></td>
              <td style="padding:6px 14px">
                <select id="cond-{card['id']}" style="padding:5px 8px;border:1px solid #f59e0b;border-radius:4px;font-size:13px;font-weight:700">
                  <option value="LP">LP — Lightly Played</option>
                  <option value="MP">MP — Moderately Played</option>
                  <option value="HP">HP — Heavily Played</option>
                  <option value="DMG">DMG — Damaged</option>
                </select>
              </td>
              <td style="padding:6px 14px;font-size:12px;color:#92400e" id="played-price-{card['id']}">R {price:.2f}</td>
              <td style="padding:6px 14px;font-size:12px;color:#888">0</td>
              <td style="padding:6px 14px">
                <input type="number" id="played-qty-{card['id']}" min="1" value="1" placeholder="Qty"
                  style="width:70px;padding:6px;border:1px solid #f59e0b;border-radius:4px;font-size:14px;font-weight:600;text-align:center">
              </td>
              <td style="padding:6px 14px">
                <button onclick="savePlayed({card['id']},{card['price']})" style="background:#10B981;color:#fff;border:none;border-radius:4px;padding:6px 14px;cursor:pointer;font-size:13px;font-weight:700">Save</button>
                <button onclick="document.getElementById('played-row-{card['id']}').style.display='none'" style="background:#6b7280;color:#fff;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;font-size:12px;margin-left:4px">✕</button>
              </td>
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
  if(!confirm('Wipe stock to 0 for this card?'))return;
  fetch('/api/stock/delete/'+id+'/',{{method:'POST',headers:{{'X-CSRFToken':getCookie('csrftoken')}}}})
  .then(r=>r.json()).then(d=>{{
    if(d.success){{
      const row=btn.closest('tr');
      row.querySelector('td:nth-child(6)').textContent='0';
      showMsg('Stock wiped to 0',true);
    }}else alert('Failed to wipe stock');
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
const COND_MULT = {{LP:0.80,MP:0.60,HP:0.35,DMG:0.20}};
function addPlayed(id,tcgId,basePrice,btn){{
  const row=document.getElementById('played-row-'+id);
  row.style.display=row.style.display==='none'?'table-row':'none';
  const sel=document.getElementById('cond-'+id);
  const priceEl=document.getElementById('played-price-'+id);
  function updatePrice(){{
    const mult=COND_MULT[sel.value]||0.80;
    priceEl.textContent='R '+(basePrice*mult).toFixed(2);
  }}
  sel.onchange=updatePrice;
  updatePrice();
}}
function savePlayed(nmId,basePrice){{
  const cond=document.getElementById('cond-'+nmId).value;
  const qty=parseInt(document.getElementById('played-qty-'+nmId).value)||1;
  const mult=COND_MULT[cond]||0.80;
  const price=(basePrice*mult).toFixed(2);
  fetch('/api/stock/played/',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')}},
    body:JSON.stringify({{nm_product_id:nmId,condition:cond,stock:qty,price:parseFloat(price)}})
  }}).then(r=>r.json()).then(d=>{{
    if(d.ok){{showMsg('Played copy saved! ID: '+d.product_id+' · '+cond+' · R'+price+' · Qty '+qty,true);
      document.getElementById('played-row-'+nmId).style.display='none';
    }}else showMsg('Error: '+d.error,false);
  }});
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
            p.stock = 0
            p.save(update_fields=['stock'])
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


@csrf_exempt
@staff_member_required
@require_POST
def stock_add_played(request):
    """Create a played-condition copy of an existing NM product."""
    try:
        data = json.loads(request.body)
        nm_id = int(data['nm_product_id'])
        condition = data['condition']
        stock = max(1, int(data.get('stock', 1)))
        price = float(data['price'])

        if condition not in ('LP', 'MP', 'HP', 'DMG'):
            return JsonResponse({'ok': False, 'error': 'Invalid condition'})

        nm = PokemonProduct.objects.select_related('card_set', 'card_set__era', 'category').get(id=nm_id)

        # Check if played copy already exists for this condition
        existing = PokemonProduct.objects.filter(
            tcgcsv_product_id=nm.tcgcsv_product_id,
            condition=condition,
            variant_override=nm.variant_override,
        ).exclude(id=nm_id).first()

        if existing:
            # Update stock on existing played copy
            existing.stock += stock
            existing.price = price
            existing.save(update_fields=['stock', 'price', 'updated_at'])
            return JsonResponse({'ok': True, 'product_id': existing.id, 'action': 'updated'})

        # Create new played product row
        played = PokemonProduct(
            name=nm.name,
            name_japanese=nm.name_japanese,
            card_set=nm.card_set,
            category=nm.category,
            rarity=nm.rarity,
            condition=condition,
            variant_override=nm.variant_override,
            variant_sort=nm.variant_sort,
            card_number=nm.card_number,
            number=nm.number,
            pokedex_number=nm.pokedex_number,
            supertype=nm.supertype,
            card_subtypes=nm.card_subtypes,
            image_url=nm.image_url,
            image_small_url=nm.image_small_url,
            tcgcsv_product_id=nm.tcgcsv_product_id,
            price=price,
            stock=stock,
            is_active=True,
            legal_standard=nm.legal_standard,
            legal_expanded=nm.legal_expanded,
            legal_unlimited=nm.legal_unlimited,
        )
        played.save()

        # Copy pokemon types
        if nm.pokemon_types.exists():
            played.pokemon_types.set(nm.pokemon_types.all())

        return JsonResponse({'ok': True, 'product_id': played.id, 'action': 'created'})

    except PokemonProduct.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'NM product not found'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


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


@staff_member_required
def checklist_stock(request):
    # NOTE (flagged by Claude, 2026-06-20): a second function named
    # `checklist_stock` is defined further down this file (the JsonResponse
    # API endpoint for checking stock by tcgcsv_product_id). Because Python
    # binds the name at module load time, that LATER definition silently
    # overwrites this one — meaning this HTML staff page is currently
    # UNREACHABLE from urls.py, even though the URL route still resolves
    # without error. Rename one of these two functions (and update
    # urls.py / any templates referencing it) to restore this page.
    """Stock checklist — shows all cards per set with current stock levels."""
    from .models import CardSet
    set_code = request.GET.get('set', '')
    sets = CardSet.objects.filter(
        products__isnull=False
    ).distinct().order_by('-release_date', 'name')

    products = []
    selected_set = None
    if set_code:
        selected_set = CardSet.objects.filter(code=set_code).first()
        if selected_set:
            products = list(
                PokemonProduct.objects
                .filter(card_set__code=set_code)
                .order_by('card_number', 'variant_sort')
                .values('id', 'name', 'number', 'variant_sort', 'rarity', 'stock', 'price', 'condition')
            )

    rows = ''
    for p in products:
        stock_val = p['stock'] or 0
        stock_color = '#22c55e' if stock_val > 0 else '#ef4444'
        rows += f'''<tr style="border-bottom:1px solid #2a2a3a">
            <td style="padding:6px 10px;font-size:12px;color:#a0a0b0">{p["number"] or "-"}</td>
            <td style="padding:6px 10px;font-size:12px;color:#fff">{p["name"]}</td>
            <td style="padding:6px 10px;font-size:12px;color:#a0a0b0">{p["variant_sort"] or "N"}</td>
            <td style="padding:6px 10px;font-size:12px;color:#a0a0b0">{p["rarity"] or "-"}</td>
            <td style="padding:6px 10px;font-size:12px;color:#a0a0b0">{p["condition"] or "NM"}</td>
            <td style="padding:6px 10px;font-size:12px;font-weight:bold;color:{stock_color}">{stock_val}</td>
            <td style="padding:6px 10px;font-size:12px;color:#a0a0b0">R {float(p["price"] or 0):.2f}</td>
        </tr>'''

    set_options = ''.join(
        f'<option value="{s.code}" {"selected" if s.code == set_code else ""}>{s.name} ({s.code})</option>'
        for s in sets
    )

    total_in_stock = sum(1 for p in products if (p['stock'] or 0) > 0)
    total_cards = len(products)

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Stock Checklist</title>
<style>body{{background:#0e0e16;color:#fff;font-family:Arial,sans-serif;margin:0;padding:20px}}
select,button{{background:#1a1a2e;color:#fff;border:1px solid #2a2a3a;padding:8px 14px;border-radius:6px;font-size:13px}}
button{{background:#ff6b35;border-color:#ff6b35;cursor:pointer;font-weight:bold}}
table{{width:100%;border-collapse:collapse}}
th{{background:#1a1a2e;padding:8px 10px;font-size:11px;text-align:left;color:#a0a0b0;text-transform:uppercase;letter-spacing:.05em}}
</style></head><body>
<div style="max-width:900px;margin:0 auto">
<h2 style="color:#ff6b35;margin-bottom:20px">📋 Stock Checklist</h2>
<form method="get" style="display:flex;gap:12px;align-items:center;margin-bottom:24px">
  <select name="set" style="flex:1;max-width:400px">
    <option value="">— Select a Set —</option>
    {set_options}
  </select>
  <button type="submit">View</button>
  {"" if not set_code else f'<a href="?set={set_code}&fmt=print" target="_blank" style="background:#333;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none;font-size:13px;border:1px solid #555">🖨 Print</a>'}
</form>
{"" if not selected_set else f'<div style="margin-bottom:16px;color:#a0a0b0;font-size:13px"><strong style="color:#fff">{selected_set.name}</strong> &nbsp;|&nbsp; {total_in_stock} / {total_cards} cards in stock</div>'}
{"<p style='color:#555;font-size:13px'>Select a set above to view its stock checklist.</p>" if not set_code else f"""
<table>
  <thead><tr>
    <th>#</th><th>Card Name</th><th>Variant</th><th>Rarity</th><th>Condition</th><th>Stock</th><th>Price</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""}
</div></body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')


from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def checklist_stock(request):
    # NOTE (flagged by Claude, 2026-06-20): this function shares its name
    # with the HTML staff checklist page defined earlier in this file.
    # This is the one urls.py actually resolves to right now — the other
    # one is dead code until the names are made unique.
    raw = request.GET.get('product_ids', '')
    if not raw:
        return JsonResponse([], safe=False)
    try:
        pids = [int(p.strip()) for p in raw.split(',') if p.strip().isdigit()]
    except ValueError:
        return JsonResponse({'error': 'Invalid'}, status=400)
    if not pids:
        return JsonResponse([], safe=False)
    pids = pids[:1000]
    from products.models import PokemonProduct
    in_stock = list(PokemonProduct.objects.filter(tcgcsv_product_id__in=pids, stock__gt=0).values_list('tcgcsv_product_id', flat=True))
    return JsonResponse(in_stock, safe=False)




# --- Set management page: per-row and bulk variant apply / delete ---------

VARIANT_LABEL_FULL = {
    'N': 'Normal', 'H': 'Holo', 'RH': 'Reverse Holo',
    'PB': 'Poke Ball', 'MB': 'Master Ball', 'LB': 'Love Ball',
    'FB': 'Friend Ball', 'QB': 'Quick Ball', 'UB': 'Ultra Ball',
    'DB': 'Dusk Ball', 'TR': 'Team Rocket', 'SE': 'Secret',
    'PBP': 'PB Pattern', 'MBP': 'MB Pattern',
    'CC': 'Code Card', 'TT': 'Trick or Trade',
}


def _build_manage_set_dropdown_html(selected_set_code):
    """Era-grouped <option> list, same structure/ordering as stock_entry's dropdown."""
    all_sets = sorted(
        list(
            CardSet.objects
            .select_related('era')
            .annotate(card_count=Count('products'))
        ),
        key=lambda s: s.release_date if isinstance(s.release_date, date_type) else date_type(1900, 1, 1),
        reverse=True
    )
    sets_with_cards = [s for s in all_sets if s.card_count > 0]
    sets_empty = [s for s in all_sets if s.card_count == 0]

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

    other_eras = set(by_era.keys()) - set(ERA_ORDER)
    if other_eras:
        options_html += '<optgroup label="Other">'
        for era_code in sorted(other_eras):
            for s in by_era[era_code]:
                sel = 'selected' if s.code == selected_set_code else ''
                options_html += f'<option value="{s.code}" {sel}>[{s.code}] {s.name} ({s.card_count})</option>'
        options_html += '</optgroup>'

    if sets_empty:
        options_html += '<optgroup label="Empty Sets">'
        for s in sets_empty:
            sel = 'selected' if s.code == selected_set_code else ''
            options_html += f'<option value="{s.code}" {sel}>[{s.code}] {s.name}</option>'
        options_html += '</optgroup>'

    return options_html


@staff_member_required
def manage_set(request):
    from django.middleware.csrf import get_token
    csrf_token = get_token(request)

    selected_set_code = request.GET.get('set', '').strip()
    message = ''
    card_set = None

    if selected_set_code:
        card_set = CardSet.objects.filter(code=selected_set_code).first()
        if not card_set:
            message = f'Set "{selected_set_code}" not found.'
            selected_set_code = ''

    if request.method == 'POST' and card_set:
        action = request.POST.get('action')

        if action in ('delete_single', 'apply_variant_single'):
            try:
                product_id = int(request.POST.get('product_id', ''))
            except (TypeError, ValueError):
                product_id = None

            p = PokemonProduct.objects.filter(id=product_id, card_set=card_set).first() if product_id else None
            if not p:
                message = 'Product not found — nothing changed.'
            elif action == 'delete_single':
                name = p.name
                p.delete()
                message = f'Deleted "{name}".'
            else:
                new_variant = request.POST.get('variant_value', '').strip()
                if not new_variant:
                    message = 'No variant chosen — nothing changed.'
                else:
                    p.variant_override = new_variant
                    new_pb_id = p.generate_pb_id()
                    if new_pb_id:
                        p.pb_id = new_pb_id
                    p.save()
                    message = f"Applied variant '{new_variant}' to \"{p.name}\"."

        elif action in ('delete', 'apply_variant'):
            selected_ids = [int(i) for i in request.POST.getlist('selected') if i.isdigit()]
            if not selected_ids:
                message = 'No products were selected — nothing changed.'
            else:
                qs = PokemonProduct.objects.filter(id__in=selected_ids, card_set=card_set)
                if action == 'delete':
                    deleted_count = qs.count()
                    qs.delete()
                    message = f'Deleted {deleted_count} product(s).'
                else:
                    new_variant = request.POST.get('variant_value', '').strip()
                    if not new_variant:
                        message = 'No variant was chosen — nothing changed.'
                    else:
                        updated = 0
                        with transaction.atomic():
                            for p in qs:
                                p.variant_override = new_variant
                                new_pb_id = p.generate_pb_id()
                                if new_pb_id:
                                    p.pb_id = new_pb_id
                                p.save()
                                updated += 1
                        message = f"Applied variant '{new_variant}' to {updated} product(s)."
        else:
            message = 'Unrecognized action — nothing changed.'

    dropdown_html = _build_manage_set_dropdown_html(selected_set_code)
    msg_html = f'<div class="msg">{message}</div>' if message else ''

    if not card_set:
        html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Manage Sets - PokeBulk SA</title>
<style>
* {{ box-sizing:border-box }}
body {{ font-family:Arial,sans-serif;background:#0d0d12;color:#eee;padding:24px;margin:0 }}
select {{ background:#1a1a24;border:1px solid #2a2a3a;color:#fff;padding:8px 12px;border-radius:6px;font-size:14px;width:100% }}
optgroup {{ color:#ff6b35 }}
.box {{ background:#14141c;border-radius:8px;padding:20px;max-width:600px }}
.msg {{ background:#1a1a24;border-left:3px solid #ff6b35;padding:10px 14px;border-radius:6px;margin-bottom:16px;font-size:13px }}
</style></head><body>
<h1 style="font-size:20px;margin-bottom:16px">Manage Set Products</h1>
{msg_html}
<div class="box">
  <form method="get">
    <select name="set" onchange="this.form.submit()">{dropdown_html}</select>
  </form>
</div>
</body></html>'''
        return HttpResponse(html, content_type='text/html; charset=utf-8')

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

    variant_options = ''.join(
        f'<option value="{code}">{code} - {label}</option>'
        for code, label in VARIANT_LABEL_FULL.items()
    )

    rows = ''
    for p in products:
        img = p.image_small_url or p.image_url or ''
        if img:
            img_tag = f'<img src="{img}" style="width:36px;height:50px;object-fit:cover;border-radius:4px;background:#222">'
        else:
            img_tag = '<div style="width:36px;height:50px;background:#333;border-radius:4px"></div>'
        stock_color = '#4ade80' if p.stock > 0 else '#f43f5e'
        variant_display = p.variant_override or '-'
        variant_label = VARIANT_LABEL_FULL.get(p.variant_override, '')

        row_variant_options = ''.join(
            f'<option value="{code}" {"selected" if code == p.variant_override else ""}>{code} - {label}</option>'
            for code, label in VARIANT_LABEL_FULL.items()
        )

        rows += f'''<tr style="border-bottom:1px solid #2a2a3a">
            <td style="padding:6px 8px"><input type="checkbox" name="selected" value="{p.id}" form="bulk-form"></td>
            <td style="padding:6px 8px">{img_tag}</td>
            <td style="padding:6px 8px;font-size:12px">{p.card_number if p.card_number is not None else '--'}</td>
            <td style="padding:6px 8px;font-size:12px">{p.name}</td>
            <td style="padding:6px 8px;font-size:12px">{p.get_rarity_display()}</td>
            <td style="padding:6px 8px;font-size:12px;font-weight:bold" title="{variant_label}">{variant_display}</td>
            <td style="padding:6px 8px;font-size:12px;color:#888">{p.variant_sort}</td>
            <td style="padding:6px 8px;font-size:12px;color:{stock_color};font-weight:bold">{p.stock}</td>
            <td style="padding:6px 8px;font-size:12px">R {p.price:.2f}</td>
            <td style="padding:6px 8px;font-size:10px;color:#888">{p.pb_id}</td>
            <td style="padding:6px 8px;font-size:10px;color:#888">{p.id}</td>
            <td style="padding:6px 8px;white-space:nowrap">
              <form method="post" action="?set={selected_set_code}" style="display:inline-flex;gap:4px;align-items:center;margin:0">
                <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                <input type="hidden" name="action" value="apply_variant_single">
                <input type="hidden" name="product_id" value="{p.id}">
                <select name="variant_value" style="padding:3px 4px;font-size:11px">{row_variant_options}</select>
                <button type="submit" style="background:#2a2a3a;color:#fff;border:none;padding:3px 8px;border-radius:4px;font-size:11px;cursor:pointer">Apply</button>
              </form>
              <form method="post" action="?set={selected_set_code}" style="display:inline;margin:0" onsubmit="return confirm('Delete this product? This cannot be undone.')">
                <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                <input type="hidden" name="action" value="delete_single">
                <input type="hidden" name="product_id" value="{p.id}">
                <button type="submit" style="background:#dc2626;color:#fff;border:none;padding:3px 8px;border-radius:4px;font-size:11px;cursor:pointer;margin-left:4px">Delete</button>
              </form>
            </td>
        </tr>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Manage {card_set.code} - PokeBulk SA</title>
<style>
* {{ box-sizing:border-box }}
body {{ font-family:Arial,sans-serif;background:#0d0d12;color:#eee;padding:0;margin:0 }}
table {{ border-collapse:collapse;width:100%;background:#14141c }}
th {{ background:#1a1a24;font-size:11px;text-align:left;padding:8px;color:#a0a0b0;border-bottom:1px solid #2a2a3a;position:sticky;top:118px;z-index:90 }}
input[type=text] {{ background:#0d0d12;border:1px solid #2a2a3a;color:#fff;padding:6px 10px;border-radius:6px }}
select {{ background:#0d0d12;border:1px solid #2a2a3a;color:#fff;padding:6px 10px;border-radius:6px }}
button {{ background:#ff6b35;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold }}
button.danger {{ background:#dc2626 }}
button.secondary {{ background:#2a2a3a;font-weight:normal }}
.msg {{ background:#1a1a24;border-left:3px solid #ff6b35;padding:10px 14px;border-radius:6px;font-size:13px }}
.topbar {{ position:sticky;top:0;z-index:100;background:#0d0d12;padding:16px 20px;border-bottom:1px solid #2a2a3a;box-shadow:0 4px 10px rgba(0,0,0,0.4) }}
.content {{ padding:0 20px 20px }}
optgroup {{ color:#ff6b35 }}
</style>
</head><body>

<div class="topbar">
  <h1 style="font-size:18px;margin-bottom:8px">Manage Set: {card_set.name} [{card_set.code}]</h1>
  <form method="get" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
    <select name="set" onchange="this.form.submit()" style="min-width:260px">{dropdown_html}</select>
    <input type="text" name="q" placeholder="Search card name..." value="{search}">
    <select name="stock" onchange="this.form.submit()">
      <option value="" {"selected" if stock_filter == "" else ""}>All stock</option>
      <option value="in" {"selected" if stock_filter == "in" else ""}>In stock only</option>
      <option value="out" {"selected" if stock_filter == "out" else ""}>Out of stock only</option>
    </select>
    <button type="submit">Filter</button>
  </form>
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <button type="button" class="secondary" onclick="document.querySelectorAll('input[name=selected]').forEach(c=>c.checked=true)">Select All</button>
    <button type="button" class="secondary" onclick="document.querySelectorAll('input[name=selected]').forEach(c=>c.checked=false)">Select None</button>
    <select name="variant_value" form="bulk-form">
      <option value="">-- choose variant --</option>
      {variant_options}
    </select>
    <button type="submit" form="bulk-form" name="action" value="apply_variant" onclick="return confirm('Apply the selected variant to all checked products?')">Apply Variant (bulk)</button>
    <button type="submit" form="bulk-form" name="action" value="delete" class="danger" onclick="return confirm('Permanently delete all checked products? This cannot be undone.')">Delete Selected (bulk)</button>
  </div>
  {msg_html}
  <div style="color:#888;font-size:12px;margin-top:6px">{len(products)} product(s) shown</div>
</div>

<form method="post" id="bulk-form" action="?set={selected_set_code}">
  <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
</form>

<div class="content">
  <table>
    <thead><tr>
      <th></th><th>Image</th><th>Card #</th><th>Name</th><th>Rarity</th><th>Variant</th><th>Sort</th><th>Stock</th><th>Price</th><th>pb_id</th><th>ID</th><th>Row actions</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
</body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')
