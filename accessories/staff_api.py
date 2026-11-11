"""
accessories/staff_api.py -- 2026-11-11

Staff-only accessory management for /staff/accessories (Michael: adjusting an
accessory's price "must work through Staff"). Unlike the public catalogue
this lists EVERYTHING, including out-of-stock and inactive items.

    GET   /api/accessories-admin/?search=&category=
    PATCH /api/accessories-admin/<id>/   {price, stock, is_active, name, description, manufacturer, category}

Saves through Accessory.save(), so the Pile product row (cart_link) follows
price/stock/active. A hand-edited price sets price_locked so the TCGCSV sync
never overwrites it.
"""
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .cart_link import refresh_accessory_stock
from .models import Accessory

EDITABLE = ["name", "description", "manufacturer", "category", "price", "stock", "is_active"]


def _row(a):
    return {
        "id": a.id, "sku": a.sku, "name": a.name, "category": a.category,
        "category_display": a.get_category_display(), "manufacturer": a.manufacturer,
        "description": a.description, "image_url": a.image_url,
        "price": str(a.price), "stock": a.stock, "is_active": a.is_active,
        "price_locked": a.price_locked,
    }


@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_accessories(request):
    refresh_accessory_stock()  # Pile sales move the product row's stock
    qs = Accessory.objects.all().order_by("category", "name")
    q = (request.query_params.get("search") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(manufacturer__icontains=q))
    cat = request.query_params.get("category")
    if cat:
        qs = qs.filter(category=cat)
    return Response({
        "categories": [{"value": v, "label": l} for v, l in Accessory.CATEGORY_CHOICES],
        "results": [_row(a) for a in qs],
    })


@api_view(["PATCH"])
@permission_classes([IsAdminUser])
def staff_accessory_detail(request, pk):
    try:
        a = Accessory.objects.get(pk=pk)
    except Accessory.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)
    refresh_accessory_stock()
    a.refresh_from_db()
    d = request.data
    if "price" in d:
        try:
            p = Decimal(str(d["price"]))
        except InvalidOperation:
            return Response({"detail": "Price must be a number."}, status=400)
        if p < 0:
            return Response({"detail": "Price can't be negative."}, status=400)
        if p != a.price:
            a.price = p
            a.price_locked = True
    if "stock" in d:
        try:
            s = int(d["stock"])
        except (TypeError, ValueError):
            return Response({"detail": "Stock must be a whole number."}, status=400)
        if s < 0:
            return Response({"detail": "Stock can't be negative."}, status=400)
        a.stock = s
    if "is_active" in d:
        a.is_active = bool(d["is_active"])
    for f in ("name", "description", "manufacturer"):
        if f in d:
            setattr(a, f, str(d[f]).strip())
    if "category" in d:
        if d["category"] not in {c for c, _ in Accessory.CATEGORY_CHOICES}:
            return Response({"detail": "Unknown category."}, status=400)
        a.category = d["category"]
    if not a.name:
        return Response({"detail": "Name can't be empty."}, status=400)
    a.save()
    return Response(_row(a))
