from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import PokemonProduct
from .models import Cart, CartItem, Order, OrderItem, OrderTracking
from .serializers import (
    CartSerializer, CartItemSerializer, OrderSerializer,
    OrderStatusUpdateSerializer
)



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
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items = cart.items.select_related('product').all()
        items = [i for i in items if i.product is not None]
        if not items:
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
                product_name=item.product.name,
                product_sku=item.product.csv_sku or '',
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
    ).order_by('product__card_set__era__code', 'product__card_set__name', 'product__card_number', 'product_name'))

    null_skus = [i.product_sku for i in items if i.product is None and i.product_sku]
    sku_lookup = {}
    if null_skus:
        from products.models import PokemonProduct as PP
        found = PP.objects.filter(sku__in=null_skus).select_related('card_set', 'card_set__era')
        sku_lookup = {p.sku: p for p in found}

    def get_set_key(item):
        if item.product and item.product.card_set:
            return (item.product.card_set.name, item.product.card_set.code)
        p = sku_lookup.get(item.product_sku)
        if p and p.card_set:
            return (p.card_set.name, p.card_set.code)
        return ('Unknown Set', '???')

    def get_item_display(item):
        if item.product:
            p = item.product
        else:
            p = sku_lookup.get(item.product_sku)
        if p:
            num = str(p.card_number or '').zfill(3)
            var = p.variant_sort or 'N'
            name = p.name
        else:
            num = '--'
            var = '?'
            name = item.product_name or item.product_sku or 'Unknown card'
        return num, name, var

    sets_html = ''
    for (set_name, set_code), group in groupby(sorted(items, key=get_set_key), key=get_set_key):
        cards = list(group)
        line_count = len(cards)
        total_qty = sum(item.quantity for item in cards)
        rows = ''
        for i, item in enumerate(cards, 1):
            num, name, var = get_item_display(item)
            var_colors = {'N': '#e8e8e8;color:#333', 'H': '#fff3cd;color:#856404', 'RH': '#e8e4ff;color:#4c3d99'}
            var_style = var_colors.get(var, '#e8e8e8;color:#333')
            rows += f'''<tr>
              <td>{i}</td><td>{num}</td><td>{name}</td>
              <td><span style="background:{var_style};padding:1px 6px;border-radius:8px;font-size:9px;font-weight:bold">{var}</span></td>
              <td>{item.quantity}</td><td>R {item.price_at_purchase:.2f}</td>
              <td style="font-size:13px">[ ]</td>
            </tr>'''

        if total_qty != line_count:
            set_count_label = f'{line_count} line{"s" if line_count != 1 else ""} / {total_qty} card{"s" if total_qty != 1 else ""} total'
        else:
            set_count_label = f'{total_qty} card{"s" if total_qty != 1 else ""}'

        sets_html += f'''<div style="margin-bottom:6px">
          <h3 style="font-size:13px;background:#f0f0f0;padding:3px 8px;border-left:3px solid #ff6b35;margin-bottom:2px">{set_name} [{set_code}] ({set_count_label})</h3>
          <table style="width:100%;border-collapse:collapse">
            <thead><tr style="background:#eee">
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="40">#</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="60">Card #</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc">Card Name</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="70">Variant</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="40">Qty</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="110">Price</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="30">Done</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table></div>'''

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
<html><head><meta charset="utf-8"><title>Order #{order.id} - PokeBulk SA</title>
<style>* {{ margin:0;padding:0;box-sizing:border-box }} body {{ font-family:Arial,sans-serif;font-size:12px;color:#000;padding:14px;line-height:1.2 }} table {{ border-collapse:collapse }} table td {{ padding:2px 8px;border-bottom:1px solid #eee;font-size:11px }} @media print {{ .no-print {{ display:none }} @page {{ margin:10mm;size:A4 }} }}</style>
</head><body>
<div class="no-print" style="margin-bottom:16px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-size:14px;cursor:pointer">Print</button>
  <button onclick="window.close()" style="margin-left:8px;padding:8px 20px;border-radius:6px;border:1px solid #ccc;cursor:pointer">Close</button>
</div>
<div style="display:flex;justify-content:space-between;margin-bottom:10px;border-bottom:2px solid #000;padding-bottom:8px">
  <div>
    <h1 style="font-size:20px;margin-bottom:4px">PokeBulk SA - Packing Slip</h1>
    <div style="font-size:12px;color:#444;margin-top:2px">Order #{order.id} | {order.created_at.strftime("%d %b %Y %H:%M")} | {item_count} cards</div>
    <div style="font-size:12px;color:#444">Customer: <strong>{order.user.username}</strong> ({order.user.email})</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:24px;font-weight:bold;color:#ff6b35">R {order.total_price:.2f}</div>
    <div style="font-size:12px;color:#444">{order.get_delivery_method_display()}</div>
    <div style="font-size:12px;color:#444">Status: {order.get_status_display()}</div>
  </div>
</div>
<div style="border:1px solid #ccc;padding:6px 10px;border-radius:4px;margin-bottom:8px;font-size:11px;line-height:1.3">
  <strong>Delivery Details</strong><br>{delivery_info}
</div>
{"<div style='border:1px solid #ff6b35;padding:6px 10px;border-radius:4px;margin-bottom:8px;font-size:11px;line-height:1.3'><strong>Customer Note</strong><br>" + order.customer_note + "</div>" if order.customer_note else ""}
<h2 style="margin-bottom:4px;font-size:14px">Cards to Pack - Grouped by Set</h2>
{sets_html}
<table style="width:100%;border-collapse:collapse;margin-top:4px">
  <tr style="font-weight:bold;background:#f9f9f9"><td colspan="5" style="text-align:right;padding:4px 8px">Subtotal</td><td style="padding:4px 8px">R {subtotal:.2f}</td><td></td></tr>
  <tr style="font-weight:bold;background:#f9f9f9"><td colspan="5" style="text-align:right;padding:4px 8px">Shipping</td><td style="padding:4px 8px">R {shipping:.2f}</td><td></td></tr>
  <tr style="font-weight:bold;font-size:14px"><td colspan="5" style="text-align:right;padding:4px 8px">TOTAL</td><td style="padding:4px 8px;color:#ff6b35">R {order.total_price:.2f}</td><td></td></tr>
</table>
<div style="margin-top:10px;border-top:1px solid #ccc;padding-top:6px;font-size:10px;color:#666">
  Printed: {printed_at} | PokeBulk SA - Birchleigh North, Kempton Park | enquiries@pokebulk.co.za
</div>
</body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')



@staff_member_required
def print_invoice(request, order_id):
    from django.utils import timezone
    order = get_object_or_404(Order, id=order_id)
    items = list(order.items.select_related(
        'product', 'product__card_set', 'product__card_set__era'
    ).order_by('product__card_set__name', 'product__card_number'))

    null_skus = [i.product_sku for i in items if i.product is None and i.product_sku]
    sku_lookup = {}
    if null_skus:
        from products.models import PokemonProduct as PP
        found = PP.objects.filter(sku__in=null_skus).select_related('card_set')
        sku_lookup = {p.sku: p for p in found}

    rows = ''
    for i, item in enumerate(items, 1):
        p = item.product or sku_lookup.get(item.product_sku)
        if p is not None:
            num = str(p.card_number or '').zfill(3)
            var = p.variant_sort or 'N'
            set_name = p.card_set.name if p.card_set else '-'
            set_code = p.card_set.code if p.card_set else ''
            rarity = (p.rarity or '').replace('_', ' ').title()
            name = p.name
        else:
            num = '--'; var = '?'; set_name = '-'; set_code = ''; rarity = ''; name = item.product_name or item.product_sku or 'Unknown card'
        rows += f'''<tr style="border-bottom:1px solid #eee">
            <td style="padding:2px 8px;font-size:11px">{i}</td>
            <td style="padding:2px 8px;font-size:11px">{set_name} [{set_code}]</td>
            <td style="padding:2px 8px;font-size:11px">#{num}</td>
            <td style="padding:2px 8px;font-size:11px">{name}</td>
            <td style="padding:2px 8px;font-size:11px">{rarity}</td>
            <td style="padding:2px 8px;font-size:11px">{var}</td>
            <td style="padding:2px 8px;font-size:11px;text-align:center">{item.quantity}</td>
            <td style="padding:2px 8px;font-size:11px;text-align:right">R {item.price_at_purchase:.2f}</td>
            <td style="padding:2px 8px;font-size:11px;text-align:right">R {float(item.price_at_purchase) * item.quantity:.2f}</td>
        </tr>'''

    subtotal = sum(float(item.price_at_purchase) * item.quantity for item in items)
    shipping = float(order.shipping_cost or 0)
    total = subtotal + shipping
    item_count = sum(i.quantity for i in items)
    invoice_date = order.created_at.strftime('%d-%m-%Y')
    invoice_num = f'INV {order.id:08d}'
    customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.username
    customer_email = order.user.email
    phone = getattr(order.user, 'phone_number', '') or ''

    if order.delivery_method == 'collection':
        delivery_label = 'Local Collection'
        delivery_detail = 'Birchleigh North, Kempton Park'
    elif order.pudo_locker_name:
        delivery_label = order.get_shipping_method_display()
        delivery_detail = f'{order.pudo_locker_name}<br>{order.pudo_locker_address or ""}'
    else:
        parts = [order.delivery_address_line1, order.delivery_address_line2,
                 order.delivery_city, order.delivery_province, order.delivery_postal_code]
        delivery_label = order.get_shipping_method_display()
        delivery_detail = ', '.join(p for p in parts if p) or '-'

    waybill_row = f'<tr><td style="color:#555;padding:1px 0;font-size:11px">Waybill</td><td style="padding:1px 0;font-size:11px;font-weight:bold">{order.waybill_number}</td></tr>' if order.waybill_number else ''
    eft_notice = '<div style="background:#f5f5f5;border-radius:6px;padding:6px 14px;margin-bottom:10px;font-size:11px;color:#333"><strong>Banking details:</strong> Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Nedbank Current &nbsp;|&nbsp; Branch: 198765 &nbsp;|&nbsp; Acc: 1301474037</div>' if order.payment_method in ['eft', 'coc'] else ''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{invoice_num} - PokeBulk SA</title>
<style>* {{ box-sizing:border-box;margin:0;padding:0 }} body {{ font-family:Arial,sans-serif;padding:16px;color:#222;font-size:12px;line-height:1.2 }} @media print {{ .no-print {{ display:none !important }} @page {{ margin:10mm;size:A4 }} }} table {{ border-collapse:collapse }} th {{ background:#f0f0f0;font-size:10px;font-weight:bold;padding:4px 8px;text-align:left;border-bottom:2px solid #ddd }}</style>
</head><body>
<div class="no-print" style="margin-bottom:16px;display:flex;gap:8px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;cursor:pointer;font-weight:bold">Print Invoice</button>
  <button onclick="window.close()" style="background:#eee;color:#333;border:none;padding:9px 16px;border-radius:6px;font-size:13px;cursor:pointer">Close</button>
</div>
<div style="display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:10px;border-bottom:3px solid #ff6b35;margin-bottom:12px">
  <div><div style="font-size:17px;font-weight:bold;color:#ff6b35">Poke Bulk SA <span style="color:#222">(Pty) Ltd</span></div>
  <div style="font-size:11px;color:#555;line-height:1.3;margin-top:2px">Reg. No: 2024/615040/07<br>4 Heloise Street, Birchleigh North, Kempton Park, 1618<br>Tel: 074 488 6919 &nbsp;|&nbsp; enquiries@pokebulk.co.za</div></div>
  <div style="text-align:right"><div style="font-size:20px;font-weight:bold;color:#333">INVOICE</div>
  <div style="font-size:13px;margin-top:2px"><strong>{invoice_num}</strong></div>
  <div style="font-size:11px;color:#555;margin-top:1px">{invoice_date}</div>
  <div style="margin-top:4px;font-size:11px;color:#555">Status: <strong>{order.get_status_display()}</strong></div></div>
</div>
{eft_notice}
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px">
  <div style="background:#f9f9f9;border-radius:6px;padding:6px 10px">
    <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:3px">Buyer</div>
    <div style="font-weight:bold;font-size:12px">{customer_name}</div>
    <div style="font-size:11px;color:#555;margin-top:1px;line-height:1.25">{customer_email}<br>{phone}</div>
  </div>
  <div style="background:#f9f9f9;border-radius:6px;padding:6px 10px">
    <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:3px">Delivery</div>
    <div style="font-weight:bold;font-size:12px">{delivery_label}</div>
    <div style="font-size:11px;color:#555;margin-top:1px;line-height:1.25">{delivery_detail}</div>
  </div>
  <div style="background:#f9f9f9;border-radius:6px;padding:6px 10px">
    <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:3px">Payment</div>
    <table style="width:100%;font-size:11px">
      <tr><td style="color:#555;padding:1px 0">Method</td><td style="font-weight:bold;padding:1px 0;text-align:right">{order.get_payment_method_display()}</td></tr>
      {waybill_row}
    </table>
  </div>
</div>
<table style="width:100%;margin-bottom:10px">
  <thead><tr><th width="30">#</th><th>Set</th><th width="60">Card #</th><th>Card name</th><th width="100">Rarity</th><th width="55">Variant</th><th width="40" style="text-align:center">Qty</th><th width="75" style="text-align:right">Unit</th><th width="80" style="text-align:right">Total</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<div style="display:flex;justify-content:flex-end;margin-bottom:12px">
  <table style="width:260px">
    <tr><td style="padding:2px 8px;color:#555">Subtotal ({item_count} items)</td><td style="padding:2px 8px;text-align:right">R {subtotal:.2f}</td></tr>
    <tr><td style="padding:2px 8px;color:#555">Shipping</td><td style="padding:2px 8px;text-align:right">{"FREE" if shipping == 0 else f"R {shipping:.2f}"}</td></tr>
    <tr style="font-weight:bold;font-size:14px;border-top:2px solid #ff6b35"><td style="padding:5px 8px">TOTAL</td><td style="padding:5px 8px;text-align:right;color:#ff6b35">R {total:.2f}</td></tr>
  </table>
</div>
<div style="border-top:1px solid #eee;padding-top:8px;font-size:10px;color:#888;text-align:center">
  Thank you for your order! &nbsp;|&nbsp; Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. No: 2024/615040/07 &nbsp;|&nbsp; enquiries@pokebulk.co.za
</div>
</body></html>'''
    return HttpResponse(html, content_type='text/html; charset=utf-8')
