"""Custom (free-form) collections -- customer-made lists of any cards, tracked on their own.
Separate from set checklists, the Pokedex and My Pokemon on purpose (2026-11-04, Michael)."""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import CustomCollection, CustomCollectionItem, PokemonProduct
from .views import _money

MAX_COLLECTIONS = 50


def _f(d):
    return float(d) if d is not None else None


def _item(it):
    p = it.product
    price = p.price or Decimal('0')
    return {
        'id': it.id,
        'product_id': p.id,
        'name': p.name,
        'number': p.number or '',
        'rarity': p.rarity,
        'variant': p.variant_override or 'N',
        'set_code': p.card_set.code if p.card_set else '',
        'set_name': p.card_set.name if p.card_set else '',
        'image_url': p.image_url or '',
        'quantity': it.quantity,
        'price': float(price),
        'value_when_added': _f(it.value_when_added),
        'price_paid': _f(it.price_paid),
        'in_stock': bool(getattr(p, 'in_stock', False)),
    }


def _totals(items):
    cards = value = paid = delta = 0
    for it in items:
        price = it.product.price or Decimal('0')
        q = it.quantity
        cards += q
        value += price * q
        if it.price_paid is not None:
            paid += it.price_paid * q
        base = it.price_paid if it.price_paid is not None else it.value_when_added
        if base is not None:
            delta += (price - base) * q
    return {'cards': cards, 'value': float(value), 'paid': float(paid), 'gain_loss': float(delta)}


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def collections_list(request):
    if request.method == 'POST':
        name = (request.data.get('name') or '').strip()[:60]
        if not name:
            return Response({'error': 'Give the collection a name'}, status=400)
        if CustomCollection.objects.filter(user=request.user).count() >= MAX_COLLECTIONS:
            return Response({'error': f'Limit of {MAX_COLLECTIONS} collections reached'}, status=400)
        c = CustomCollection.objects.create(user=request.user, name=name)
        return Response({'id': c.id, 'name': c.name, 'cards': 0, 'value': 0, 'paid': 0, 'gain_loss': 0}, status=201)
    out = []
    qs = CustomCollection.objects.filter(user=request.user).prefetch_related('items__product')
    for c in qs:
        out.append({'id': c.id, 'name': c.name, **_totals(list(c.items.all()))})
    return Response(out)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def collection_detail(request, pk):
    c = get_object_or_404(CustomCollection, pk=pk, user=request.user)
    if request.method == 'DELETE':
        c.delete()
        return Response(status=204)
    if request.method == 'PATCH':
        name = (request.data.get('name') or '').strip()[:60]
        if name:
            c.name = name
            c.save(update_fields=['name'])
    items = list(c.items.select_related('product', 'product__card_set'))
    return Response({'id': c.id, 'name': c.name, **_totals(items), 'items': [_item(i) for i in items]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def collection_add_item(request, pk):
    """Body: {"product_id": 123, "quantity"?: 1}. Adding a card already in the list adds to its quantity."""
    c = get_object_or_404(CustomCollection, pk=pk, user=request.user)
    p = get_object_or_404(PokemonProduct, pk=request.data.get('product_id'))
    try:
        qty = max(1, min(999, int(request.data.get('quantity') or 1)))
    except (TypeError, ValueError):
        qty = 1
    it, created = CustomCollectionItem.objects.get_or_create(
        collection=c, product=p, defaults={'quantity': qty, 'value_when_added': p.price})
    if not created:
        it.quantity = min(999, it.quantity + qty)
        it.save(update_fields=['quantity'])
    return Response({'id': it.id, 'quantity': it.quantity, 'created': created}, status=201 if created else 200)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def collection_item(request, pk, item_id):
    it = get_object_or_404(CustomCollectionItem, pk=item_id, collection__pk=pk, collection__user=request.user)
    if request.method == 'DELETE':
        it.delete()
        return Response(status=204)
    fields = []
    if 'quantity' in request.data:
        try:
            q = int(request.data['quantity'])
        except (TypeError, ValueError):
            return Response({'error': 'quantity must be a whole number'}, status=400)
        if q <= 0:
            it.delete()
            return Response(status=204)
        it.quantity = min(999, q)
        fields.append('quantity')
    if 'price_paid' in request.data:
        it.price_paid = _money(request.data.get('price_paid'))
        fields.append('price_paid')
    if fields:
        it.save(update_fields=fields)
    return Response({'id': it.id, 'quantity': it.quantity, 'price_paid': _f(it.price_paid)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def collection_summary(request):
    """Per-type money totals for the My Collection banner. Each type is counted on its own (Michael, 2026-11-04:
    nothing is thrown together). Sets are totalled in the browser from the static checklist data."""
    from .models import ChecklistEntry, PokedexCollectionEntry
    from accessories.sealed_collection import sealed_totals
    from accessories.models import SealedCollectionItem

    def blank():
        return {'cards': 0, 'value': 0.0, 'paid': 0.0, 'gain_loss': 0.0}

    # My Pokemon = ChecklistEntry rows under card_set "DEX-<n>", card_key = product id
    mp = blank()
    rows = list(ChecklistEntry.objects.filter(user=request.user, card_set__startswith='DEX-'))
    ids = [int(r.card_key) for r in rows if r.card_key.isdigit()]
    prices = {p['id']: (p['price'] or Decimal('0')) for p in PokemonProduct.objects.filter(id__in=ids).values('id', 'price')}
    v = paid = delta = Decimal('0')
    for r in rows:
        if not r.card_key.isdigit() or int(r.card_key) not in prices:
            continue
        price = prices[int(r.card_key)]
        mp['cards'] += 1
        v += price
        if r.price_paid is not None:
            paid += r.price_paid
        base = r.price_paid if r.price_paid is not None else r.value_when_added
        if base is not None:
            delta += price - base
    mp.update(value=float(v), paid=float(paid), gain_loss=float(delta))

    # Pokedex has no price-paid tracking yet -> value only
    pdx = blank()
    pv = Decimal('0')
    for e in PokedexCollectionEntry.objects.filter(user=request.user).select_related('product'):
        pdx['cards'] += 1
        pv += e.product.price or Decimal('0')
    pdx['value'] = float(pv)

    custom = blank()
    for c in CustomCollection.objects.filter(user=request.user).prefetch_related('items__product'):
        t = _totals(list(c.items.all()))
        for k in custom:
            custom[k] += t[k]

    st = sealed_totals(list(SealedCollectionItem.objects.filter(user=request.user).select_related('product')))
    sealed = {'cards': st['count'], 'value': st['value'], 'paid': st['paid'], 'gain_loss': st['gain_loss']}
    return Response({'pokedex': pdx, 'mypokemon': mp, 'collections': custom, 'sealed': sealed})


@api_view(['GET'])
@permission_classes([AllowAny])
def sealed_shop_facets(request):
    """Public: sets and product types that have sealed product, for the /sealed shop.
    Cross-scoped so the counts always match what you will see: sets are counted within the chosen ?type=,
    types within the chosen ?set=. ?in_stock=1 limits everything to what is currently in stock."""
    from django.db.models import Count
    base = PokemonProduct.objects.filter(supertype='Sealed', is_active=True)
    if request.GET.get('in_stock') in ('1', 'true'):
        base = base.filter(stock__gt=0)
    set_name = (request.GET.get('set') or '').strip()
    ptype = (request.GET.get('type') or '').strip()
    sets_qs = base.filter(card_subtypes=ptype) if ptype else base
    types_qs = base.filter(sealed_set_name=set_name) if set_name else base
    sets = sets_qs.exclude(sealed_set_name='').values('sealed_set_name').annotate(n=Count('id')).order_by('sealed_set_name')
    types = types_qs.exclude(card_subtypes='').values('card_subtypes').annotate(n=Count('id')).order_by('card_subtypes')
    return Response({
        'sets': [{'name': x['sealed_set_name'], 'count': x['n']} for x in sets],
        'types': [{'name': t['card_subtypes'], 'count': t['n']} for t in types],
    })
