"""Sealed Collection -- sealed products a customer owns. Separate from card collections (Michael, 2026-11-04).
Sealed products are PokemonProduct rows with supertype 'Sealed' -- the same rows the shop sells."""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from products.models import PokemonProduct
from .models import SealedCollectionItem


def _f(d):
    return float(d) if d is not None else None


def sealed_totals(items):
    count = value = paid = delta = 0
    for it in items:
        price = it.product.price or Decimal('0')
        q = it.quantity
        count += q
        value += price * q
        if it.price_paid is not None:
            paid += it.price_paid * q
        base = it.price_paid if it.price_paid is not None else it.value_when_added
        if base is not None:
            delta += (price - base) * q
    return {'count': count, 'value': float(value), 'paid': float(paid), 'gain_loss': float(delta)}


def _sealed_qs():
    return PokemonProduct.objects.filter(supertype='Sealed', is_active=True)


def _item(it):
    p = it.product
    return {
        'id': it.id, 'product_id': p.id, 'name': p.name, 'set_name': p.sealed_set_name,
        'type': p.card_subtypes, 'image_url': p.image_url or '',
        'quantity': it.quantity, 'price': float(p.price or 0), 'stock': p.stock, 'in_stock': p.stock > 0,
        'value_when_added': _f(it.value_when_added), 'price_paid': _f(it.price_paid),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sealed_list(request):
    items = list(SealedCollectionItem.objects.filter(user=request.user).select_related('product'))
    return Response({**sealed_totals(items), 'items': [_item(i) for i in items]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sealed_sets(request):
    names = (_sealed_qs().exclude(sealed_set_name='').values_list('sealed_set_name', flat=True)
             .distinct().order_by('sealed_set_name'))
    return Response(list(names))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sealed_search(request):
    """Every sealed product we know of (in stock or not -- customers may own ones we no longer carry).
    ?q= name search, ?set= exact set name (browse a whole set)."""
    q = (request.GET.get('q') or '').strip()
    set_name = (request.GET.get('set') or '').strip()
    ptype = (request.GET.get('type') or '').strip()
    qs = _sealed_qs()
    if ptype:
        qs = qs.filter(card_subtypes=ptype)
    if set_name:
        qs = qs.filter(sealed_set_name=set_name)
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(sealed_set_name__icontains=q))
    qs = qs.order_by('-stock', '-price', 'name')
    return Response([
        {'id': p.id, 'name': p.name, 'set_name': p.sealed_set_name, 'type': p.card_subtypes,
         'image_url': p.image_url or '', 'price': float(p.price or 0), 'in_stock': p.stock > 0}
        for p in qs[:300 if (set_name or ptype) else 80]
    ])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sealed_add(request):
    p = get_object_or_404(_sealed_qs(), pk=request.data.get('product_id'))
    try:
        qty = max(1, min(999, int(request.data.get('quantity') or 1)))
    except (TypeError, ValueError):
        qty = 1
    it, created = SealedCollectionItem.objects.get_or_create(
        user=request.user, product=p, defaults={'quantity': qty, 'value_when_added': p.price})
    if not created:
        it.quantity = min(999, it.quantity + qty)
        it.save(update_fields=['quantity'])
    return Response({'id': it.id, 'quantity': it.quantity, 'created': created}, status=201 if created else 200)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def sealed_item(request, item_id):
    from products.views import _money
    it = get_object_or_404(SealedCollectionItem, pk=item_id, user=request.user)
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
