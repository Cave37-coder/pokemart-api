"""Sealed Collection -- sealed products (category 'sealed') a customer owns. Separate from card collections."""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Accessory, SealedCollectionItem


def _f(d):
    return float(d) if d is not None else None


def sealed_totals(items):
    cards = value = paid = delta = 0
    for it in items:
        price = it.accessory.price or Decimal('0')
        q = it.quantity
        cards += q
        value += price * q
        if it.price_paid is not None:
            paid += it.price_paid * q
        base = it.price_paid if it.price_paid is not None else it.value_when_added
        if base is not None:
            delta += (price - base) * q
    return {'count': cards, 'value': float(value), 'paid': float(paid), 'gain_loss': float(delta)}


def _item(it):
    a = it.accessory
    return {
        'id': it.id, 'accessory_id': a.id, 'name': a.name, 'image_url': a.image_url or '',
        'quantity': it.quantity, 'price': float(a.price or 0),
        'value_when_added': _f(it.value_when_added), 'price_paid': _f(it.price_paid),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sealed_list(request):
    items = list(SealedCollectionItem.objects.filter(user=request.user).select_related('accessory'))
    return Response({**sealed_totals(items), 'items': [_item(i) for i in items]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sealed_search(request):
    """Every sealed product we know of (in stock or not -- customers may own ones we no longer carry)."""
    q = (request.GET.get('q') or '').strip()
    qs = Accessory.objects.filter(category='sealed')
    if q:
        qs = qs.filter(name__icontains=q)
    elif len(q) < 2:
        qs = qs.order_by('-created_at')
    return Response([
        {'id': a.id, 'name': a.name, 'image_url': a.image_url or '', 'price': float(a.price or 0)}
        for a in qs[:60]
    ])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sealed_add(request):
    a = get_object_or_404(Accessory, pk=request.data.get('accessory_id'), category='sealed')
    try:
        qty = max(1, min(999, int(request.data.get('quantity') or 1)))
    except (TypeError, ValueError):
        qty = 1
    it, created = SealedCollectionItem.objects.get_or_create(
        user=request.user, accessory=a, defaults={'quantity': qty, 'value_when_added': a.price})
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
