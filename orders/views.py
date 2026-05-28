from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from .models import Cart, CartItem, Order, OrderItem, OrderTracking
from .serializers import (
    CartSerializer, CartItemSerializer, OrderSerializer,
    OrderStatusUpdateSerializer
)
from products.models import PokemonProduct


class CartView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart


class CartAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        try:
            product = PokemonProduct.objects.get(id=product_id, is_active=True)
        except PokemonProduct.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        if product.stock < quantity:
            return Response({'error': 'Insufficient stock'}, status=status.HTTP_400_BAD_REQUEST)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()
        return Response(CartSerializer(cart).data)


class CartRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        try:
            item = CartItem.objects.get(id=item_id, cart__user=request.user)
            item.delete()
            return Response({'detail': 'Item removed'})
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        items = cart.items.select_related('product').all()
        if not items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        for item in items:
            if item.product.stock < item.quantity:
                return Response(
                    {'error': f'Insufficient stock for {item.product.name}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        total = sum(item.subtotal for item in items)
        payment_method = request.data.get('payment_method', 'payfast')
        shipping_method = request.data.get('shipping_method', 'pudo_locker')
        is_eft = payment_method == 'eft'
        is_coc = shipping_method == 'collection'

        order = Order.objects.create(
            user=request.user,
            total_price=total,
            status='pending_eft' if is_eft else ('awaiting_payment' if payment_method == 'payfast' else 'pending'),
            payment_method='coc' if is_coc else payment_method,
            shipping_method=shipping_method,
            shipping_cost=request.data.get('shipping_cost', 0),
            delivery_method='collection' if is_coc else 'courier',
            delivery_address_line1=request.data.get('address_line1', ''),
            delivery_address_line2=request.data.get('address_line2', ''),
            delivery_city=request.data.get('city', ''),
            delivery_province=request.data.get('province', ''),
            delivery_postal_code=request.data.get('postal_code', ''),
            pudo_locker_name=request.data.get('pudo_locker_name', ''),
            pudo_locker_address=request.data.get('pudo_locker_address', ''),
            customer_note=request.data.get('customer_note', ''),
        )
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_purchase=item.product.price,
            )
            item.product.stock -= item.quantity
            item.product.save()
        cart.items.all().delete()
        OrderTracking.objects.create(
            order=order,
            status='pending',
            note='Order received successfully.',
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related('items__product', 'tracking')


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related('items__product', 'tracking')


class OrderStatusUpdateView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        note = request.data.get('note', '')
        waybill = request.data.get('waybill_number', '')
        courier_name = request.data.get('courier_name', '')
        courier_url = request.data.get('courier_tracking_url', '')

        if new_status not in dict(Order.STATUS_CHOICES):
            return Response({'error': f'Invalid status: {new_status}'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status
        if waybill:
            order.waybill_number = waybill
        if courier_name:
            order.courier_name = courier_name
        if courier_url:
            order.courier_tracking_url = courier_url
        order.save()

        OrderTracking.objects.create(
            order=order,
            status=new_status,
            note=note,
            waybill_number=waybill,
            created_by=request.user,
        )

        return Response(OrderSerializer(order).data)


class AdminOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = Order.objects.prefetch_related('items__product', 'tracking').select_related('user')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


@staff_member_required
def print_order(request, order_id):
    from django.utils import timezone
    from itertools import groupby

    order = get_object_or_404(Order, id=order_id)
    items = list(order.items.select_related(
        'product', 'product__card_set', 'product__card_set__era'
    ).order_by('product__card_set__era__code', 'product__card_set__name', 'product__card_number'))

    # Group by set
    sets_html = ''
    for (set_name, set_code), group in groupby(items, key=lambda i: (i.product.card_set.name, i.product.card_set.code)):
        cards = list(group)
        rows = ''
        for i, item in enumerate(cards, 1):
            p = item.product
            num = str(p.card_number or '').zfill(3) if str(p.card_number or '').isdigit() else str(p.card_number or '--')
            var = p.variant_override or 'N'
            var_colors = {'N': '#e8e8e8;color:#333', 'H': '#fff3cd;color:#856404', 'RH': '#e8e4ff;color:#4c3d99'}
            var_style = var_colors.get(var, '#e8e8e8;color:#333')
            rows += f'''<tr>
              <td>{i}</td><td>{num}</td><td>{p.name}</td>
              <td><span style="background:{var_style};padding:1px 6px;border-radius:8px;font-size:10px;font-weight:bold">{var}</span></td>
              <td>{item.quantity}</td><td>R {item.price_at_purchase:.2f}</td>
              <td style="font-size:16px">[ ]</td>
            </tr>'''

        sets_html += f'''<div style="margin-bottom:12px">
          <h3 style="font-size:13px;background:#f0f0f0;padding:4px 8px;border-left:3px solid #ff6b35;margin-bottom:4px">{set_name} [{set_code}] ({len(cards)} card{"s" if len(cards)!=1 else ""})</h3>
          <table style="width:100%;border-collapse:collapse">
            <thead><tr style="background:#eee">
              <th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="40">#</th>
              <th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="60">Card #</th>
              <th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc">Card Name</th>
              <th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="70">Variant</th>
              <th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="40">Qty</th>
              <th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="110">Price</th>
              <th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="30">Done</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table></div>'''

    # Delivery info
    if order.delivery_method == 'collection':
        delivery_info = 'LOCAL COLLECTION - Birchleigh North, Kempton Park'
    else:
        parts = [order.delivery_address_line1, order.delivery_address_line2,
                 order.delivery_city, order.delivery_province, order.delivery_postal_code]
        delivery_info = ', '.join(p for p in parts if p) or order.customer_note or '-- no address provided --'

    subtotal = sum(item.price_at_purchase * item.quantity for item in items)
    shipping = order.total_price - subtotal
    item_count = sum(i.quantity for i in items)
    printed_at = timezone.now().strftime('%d %b %Y %H:%M')

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Order #{order.id} - PokeBulk SA</title>
<style>
* {{ margin:0;padding:0;box-sizing:border-box }}
body {{ font-family:Arial,sans-serif;font-size:13px;color:#000;padding:20px }}
table td {{ padding:4px 8px;border-bottom:1px solid #eee;font-size:12px }}
@media print {{ .no-print {{ display:none }} }}
</style></head><body>

<div class="no-print" style="margin-bottom:16px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-size:14px;cursor:pointer">Print</button>
  <button onclick="window.close()" style="margin-left:8px;padding:8px 20px;border-radius:6px;border:1px solid #ccc;cursor:pointer">Close</button>
</div>

<div style="display:flex;justify-content:space-between;margin-bottom:16px;border-bottom:2px solid #000;padding-bottom:12px">
  <div>
    <h1 style="font-size:20px;margin-bottom:4px">PokeBulk SA - Packing Slip</h1>
    <div style="font-size:12px;color:#444;margin-top:4px">Order #{order.id} | {order.created_at.strftime("%d %b %Y %H:%M")} | {item_count} cards</div>
    <div style="font-size:12px;color:#444">Customer: <strong>{order.user.username}</strong> ({order.user.email})</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:24px;font-weight:bold;color:#ff6b35">R {order.total_price:.2f}</div>
    <div style="font-size:12px;color:#444">{order.get_delivery_method_display()}</div>
    <div style="font-size:12px;color:#444">Status: {order.get_status_display()}</div>
  </div>
</div>

<div style="border:1px solid #ccc;padding:10px;border-radius:4px;margin-bottom:16px;font-size:12px">
  <strong>Delivery Details</strong><br>{delivery_info}
</div>

{"<div style='border:1px solid #ff6b35;padding:10px;border-radius:4px;margin-bottom:16px;font-size:12px'><strong>Customer Note</strong><br>" + order.customer_note + "</div>" if order.customer_note else ""}

<h2 style="margin-bottom:8px;font-size:15px">Cards to Pack - Grouped by Set</h2>
{sets_html}

<table style="width:100%;border-collapse:collapse;margin-top:8px">
  <tr style="font-weight:bold;background:#f9f9f9">
    <td colspan="5" style="text-align:right;padding:8px">Subtotal</td>
    <td style="padding:8px">R {subtotal:.2f}</td><td></td>
  </tr>
  <tr style="font-weight:bold;background:#f9f9f9">
    <td colspan="5" style="text-align:right;padding:8px">Shipping ({order.delivery_method})</td>
    <td style="padding:8px">R {shipping:.2f}</td><td></td>
  </tr>
  <tr style="font-weight:bold;font-size:15px">
    <td colspan="5" style="text-align:right;padding:8px">TOTAL</td>
    <td style="padding:8px;color:#ff6b35">R {order.total_price:.2f}</td><td></td>
  </tr>
</table>

<div style="margin-top:20px;border-top:1px solid #ccc;padding-top:12px;font-size:11px;color:#666">
  Printed: {printed_at} | PokeBulk SA - Birchleigh North, Kempton Park | enquiries@pokebulk.co.za
</div>
</body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')
