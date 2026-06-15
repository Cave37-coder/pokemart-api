import logging
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

logger = logging.getLogger(__name__)


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
        item_lines = []
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
            item_lines.append(f"  {item.quantity}x {item.product.name} @ R{item.product.price:.2f}")
        cart.items.all().delete()
        OrderTracking.objects.create(
            order=order,
            status='pending',
            note='Order received successfully.',
        )

        # Capture all values before thread
        order_id = order.id
        items_text = "\n".join(item_lines)
        customer_username = order.user.username
        customer_email = order.user.email
        payment_method_val = order.payment_method
        shipping_method_val = order.shipping_method
        total_price_val = float(order.total_price)
        address_val = f"{order.delivery_address_line1}, {order.delivery_city}, {order.delivery_province} {order.delivery_postal_code}"
        pudo_val = f"{order.pudo_locker_name} {order.pudo_locker_address}"
        note_val = order.customer_note

        def _send_emails():
            try:
                import os
                import urllib.request
                import json

                api_key = os.environ.get('RESEND_API_KEY', '')
                if not api_key:
                    logger.error(f"RESEND_API_KEY not set — skipping email for order #{order_id}")
                    return

                FROM_EMAIL = "PokeBulk SA <orders@updates.pokebulk.co.za>"

                def resend_send_html(to_list, subject, html_body):
                    payload = json.dumps({
                        "from": FROM_EMAIL,
                        "to": to_list,
                        "subject": subject,
                        "html": html_body,
                    }).encode('utf-8')
                    req = urllib.request.Request(
                        "https://api.resend.com/emails",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        return json.loads(resp.read())

                eft_banking = ''
                if payment_method_val in ['eft', 'coc']:
                    eft_banking = '''
                    <div style="background:#fff8f0;border:1px solid #ff6b35;border-radius:8px;padding:14px 18px;margin-bottom:20px;font-size:13px">
                        <strong>Banking Details:</strong><br>
                        Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Nedbank Current<br>
                        Branch: 198765 &nbsp;|&nbsp; Account: 1301474037<br>
                        <em>Please use your order number <strong>#{order_id}</strong> as payment reference.</em>
                    </div>'''

                items_rows = ''.join(
                    f'<tr><td style="padding:6px 8px;font-size:13px;border-bottom:1px solid #eee">{line.strip()}</td></tr>'
                    for line in item_lines
                )

                # ── HTML invoice email to customer ──────────────────────────
                if customer_email:
                    customer_html = f'''<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
  <div style="background:#ff6b35;padding:20px 28px">
    <div style="color:#fff;font-size:20px;font-weight:bold">PokeBulk SA</div>
    <div style="color:#fff;opacity:0.85;font-size:13px;margin-top:2px">Order Confirmation</div>
  </div>
  <div style="padding:24px 28px">
    <p style="font-size:15px;margin:0 0 16px">Hi <strong>{customer_username}</strong>, thank you for your order! 🎴</p>
    <div style="background:#f9f9f9;border-radius:8px;padding:14px 18px;margin-bottom:20px">
      <table style="width:100%;font-size:13px;border-collapse:collapse">
        <tr><td style="color:#888;padding:4px 0">Order</td><td style="font-weight:bold;text-align:right">#{order_id}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Payment</td><td style="text-align:right">{payment_method_val.upper()}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Shipping</td><td style="text-align:right">{shipping_method_val.replace("_"," ").title()}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Delivery to</td><td style="text-align:right">{pudo_val if pudo_val.strip() else address_val}</td></tr>
        <tr style="border-top:2px solid #ff6b35"><td style="font-weight:bold;padding:8px 0;font-size:15px">Total</td><td style="font-weight:bold;text-align:right;color:#ff6b35;font-size:15px">R{total_price_val:.2f}</td></tr>
      </table>
    </div>
    {eft_banking}
    <h3 style="font-size:14px;margin:0 0 10px;color:#333">Your Cards</h3>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
      {items_rows}
    </table>
    <p style="font-size:13px;color:#555;line-height:1.6">We will be in touch shortly to confirm your order and arrange delivery.<br>
    If you have any questions, reply to this email or contact us at <strong>enquiries@pokebulk.co.za</strong> / <strong>074 488 6919</strong>.</p>
  </div>
  <div style="background:#f0f0f0;padding:14px 28px;text-align:center;font-size:11px;color:#888">
    Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. 2024/615040/07 &nbsp;|&nbsp; Birchleigh North, Kempton Park
  </div>
</div>
</body></html>'''
                    resend_send_html(
                        [customer_email],
                        f"PokeBulk SA — Order #{order_id} Confirmed ✅",
                        customer_html,
                    )
                    logger.info(f"Customer HTML invoice email sent for order #{order_id} to {customer_email}")

                # ── HTML alert to shop ──────────────────────────────────────
                site_url = os.environ.get('API_URL', 'http://localhost:8000')
                admin_url = f"{site_url}/admin/orders/order/{order_id}/change/"
                print_url = f"{site_url}/print/order/{order_id}/"
                invoice_url = f"{site_url}/print/invoice/{order_id}/"

                shop_html = f'''<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
  <div style="background:#12121a;padding:20px 28px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="color:#ff6b35;font-size:18px;font-weight:bold">🔔 New Order #{order_id}</div>
      <div style="color:#a0a0b0;font-size:12px;margin-top:2px">PokeBulk SA Admin Alert</div>
    </div>
    <div style="color:#ff6b35;font-size:22px;font-weight:bold">R{total_price_val:.2f}</div>
  </div>
  <div style="padding:24px 28px">
    <div style="background:#f9f9f9;border-radius:8px;padding:14px 18px;margin-bottom:20px">
      <table style="width:100%;font-size:13px;border-collapse:collapse">
        <tr><td style="color:#888;padding:4px 0">Customer</td><td style="font-weight:bold;text-align:right">{customer_username} ({customer_email})</td></tr>
        <tr><td style="color:#888;padding:4px 0">Payment</td><td style="text-align:right">{payment_method_val.upper()}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Shipping</td><td style="text-align:right">{shipping_method_val.replace("_"," ").title()}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Delivery</td><td style="text-align:right">{pudo_val if pudo_val.strip() else address_val}</td></tr>
        {"<tr><td style='color:#888;padding:4px 0'>Note</td><td style='text-align:right'>" + note_val + "</td></tr>" if note_val else ""}
      </table>
    </div>
    <h3 style="font-size:14px;margin:0 0 10px;color:#333">Items Ordered</h3>
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
      {items_rows}
    </table>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a href="{print_url}" style="background:#ff6b35;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:13px">🖨 Print Pull Sheet</a>
      <a href="{invoice_url}" style="background:#333;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:13px">📄 Print Invoice</a>
      <a href="{admin_url}" style="background:#f0f0f0;color:#333;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:13px">⚙️ Admin</a>
    </div>
  </div>
</div>
</body></html>'''
                resend_send_html(
                    ['enquiries@pokebulk.co.za'],
                    f"🔔 New Order #{order_id} — R{total_price_val:.2f} — {customer_username}",
                    shop_html,
                )
                logger.info(f"Shop alert email sent for order #{order_id}")

            except Exception as e:
                logger.error(f"Email error for order #{order_id}: {e}", exc_info=True)

        # Send emails synchronously - don't use daemon thread (gets killed)
        _send_emails()

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
        rows = ''
        for i, item in enumerate(cards, 1):
            num, name, var = get_item_display(item)
            var_colors = {'N': '#e8e8e8;color:#333', 'H': '#fff3cd;color:#856404', 'RH': '#e8e4ff;color:#4c3d99'}
            var_style = var_colors.get(var, '#e8e8e8;color:#333')
            rows += f'''<tr>
              <td>{i}</td><td>{num}</td><td>{name}</td>
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
<style>* {{ margin:0;padding:0;box-sizing:border-box }} body {{ font-family:Arial,sans-serif;font-size:13px;color:#000;padding:20px }} table td {{ padding:4px 8px;border-bottom:1px solid #eee;font-size:12px }} @media print {{ .no-print {{ display:none }} }}</style>
</head><body>
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
  <tr style="font-weight:bold;background:#f9f9f9"><td colspan="5" style="text-align:right;padding:8px">Subtotal</td><td style="padding:8px">R {subtotal:.2f}</td><td></td></tr>
  <tr style="font-weight:bold;background:#f9f9f9"><td colspan="5" style="text-align:right;padding:8px">Shipping</td><td style="padding:8px">R {shipping:.2f}</td><td></td></tr>
  <tr style="font-weight:bold;font-size:15px"><td colspan="5" style="text-align:right;padding:8px">TOTAL</td><td style="padding:8px;color:#ff6b35">R {order.total_price:.2f}</td><td></td></tr>
</table>
<div style="margin-top:20px;border-top:1px solid #ccc;padding-top:12px;font-size:11px;color:#666">
  Printed: {printed_at} | PokeBulk SA - Birchleigh North, Kempton Park | enquiries@pokebulk.co.za
</div>
</body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')




@staff_member_required
def send_invoice(request, order_id):
    """Manually send invoice email to customer from Django admin."""
    order = get_object_or_404(Order, id=order_id)
    items = list(order.items.select_related('product', 'product__card_set').all())

    import os, urllib.request, json as _json
    api_key = os.environ.get('RESEND_API_KEY', '')
    if not api_key:
        return HttpResponse('RESEND_API_KEY not set.', status=500)

    customer_email = order.user.email
    if not customer_email:
        return HttpResponse('Customer has no email address.', status=400)

    customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.username
    invoice_num = f'INV {order.id:08d}'
    invoice_date = order.created_at.strftime('%d %b %Y')
    subtotal = sum(float(i.price_at_purchase) * i.quantity for i in items)
    shipping = float(order.shipping_cost or 0)
    total = subtotal + shipping
    item_count = sum(i.quantity for i in items)

    if order.delivery_method == 'collection':
        delivery_label = 'Local Collection — Birchleigh North, Kempton Park'
    elif order.pudo_locker_name:
        delivery_label = f'{order.get_shipping_method_display()} — {order.pudo_locker_name}, {order.pudo_locker_address}'
    else:
        parts = [order.delivery_address_line1, order.delivery_address_line2,
                 order.delivery_city, order.delivery_province, order.delivery_postal_code]
        delivery_label = ', '.join(p for p in parts if p) or '-'

    eft_banking = ''
    if order.payment_method in ['eft', 'coc']:
        eft_banking = f'''<div style="background:#fff8f0;border:1px solid #ff6b35;border-radius:8px;padding:14px 18px;margin-bottom:20px;font-size:13px">
            <strong>Banking Details:</strong><br>
            Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Nedbank Current<br>
            Branch: 198765 &nbsp;|&nbsp; Account: 1301474037<br>
            <em>Please use <strong>{invoice_num}</strong> as your payment reference.</em>
        </div>'''

    rows = ''
    for i, item in enumerate(items, 1):
        p = item.product
        name = p.name if p else (item.product_name or 'Unknown card')
        set_name = (p.card_set.name if p and p.card_set else '-')
        var = (p.variant_sort or 'N') if p else '?'
        line_total = float(item.price_at_purchase) * item.quantity
        rows += f'''<tr style="border-bottom:1px solid #eee">
            <td style="padding:6px 8px;font-size:12px">{i}</td>
            <td style="padding:6px 8px;font-size:12px">{set_name}</td>
            <td style="padding:6px 8px;font-size:12px">{name} [{var}]</td>
            <td style="padding:6px 8px;font-size:12px;text-align:center">{item.quantity}</td>
            <td style="padding:6px 8px;font-size:12px;text-align:right">R {item.price_at_purchase:.2f}</td>
            <td style="padding:6px 8px;font-size:12px;text-align:right">R {line_total:.2f}</td>
        </tr>'''

    html_body = f'''<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px">
<div style="max-width:650px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
  <div style="background:#ff6b35;padding:20px 28px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="color:#fff;font-size:20px;font-weight:bold">Poke Bulk SA (Pty) Ltd</div>
      <div style="color:#fff;opacity:0.85;font-size:12px;margin-top:2px">Reg. 2024/615040/07 &nbsp;|&nbsp; enquiries@pokebulk.co.za &nbsp;|&nbsp; 074 488 6919</div>
    </div>
    <div style="text-align:right">
      <div style="color:#fff;font-size:18px;font-weight:bold">INVOICE</div>
      <div style="color:#fff;opacity:0.9;font-size:13px">{invoice_num}</div>
      <div style="color:#fff;opacity:0.75;font-size:12px">{invoice_date}</div>
    </div>
  </div>
  <div style="padding:24px 28px">
    <div style="background:#f9f9f9;border-radius:8px;padding:14px 18px;margin-bottom:20px">
      <table style="width:100%;font-size:13px;border-collapse:collapse">
        <tr><td style="color:#888;padding:4px 0">Bill To</td><td style="font-weight:bold;text-align:right">{customer_name}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Email</td><td style="text-align:right">{customer_email}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Payment</td><td style="text-align:right">{order.get_payment_method_display()}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Delivery</td><td style="text-align:right">{delivery_label}</td></tr>
        <tr><td style="color:#888;padding:4px 0">Status</td><td style="text-align:right">{order.get_status_display()}</td></tr>
      </table>
    </div>
    {eft_banking}
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
      <thead><tr style="background:#f0f0f0">
        <th style="padding:8px;font-size:11px;text-align:left" width="30">#</th>
        <th style="padding:8px;font-size:11px;text-align:left">Set</th>
        <th style="padding:8px;font-size:11px;text-align:left">Card</th>
        <th style="padding:8px;font-size:11px;text-align:center" width="40">Qty</th>
        <th style="padding:8px;font-size:11px;text-align:right" width="80">Unit</th>
        <th style="padding:8px;font-size:11px;text-align:right" width="80">Total</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div style="display:flex;justify-content:flex-end;margin-bottom:20px">
      <table style="width:260px;font-size:13px">
        <tr><td style="padding:5px 8px;color:#555">Subtotal ({item_count} items)</td><td style="padding:5px 8px;text-align:right">R {subtotal:.2f}</td></tr>
        <tr><td style="padding:5px 8px;color:#555">Shipping</td><td style="padding:5px 8px;text-align:right">{"FREE" if shipping == 0 else f"R {shipping:.2f}"}</td></tr>
        <tr style="border-top:2px solid #ff6b35;font-weight:bold;font-size:15px">
          <td style="padding:8px">TOTAL</td>
          <td style="padding:8px;text-align:right;color:#ff6b35">R {total:.2f}</td>
        </tr>
      </table>
    </div>
    <p style="font-size:13px;color:#555;line-height:1.6">Thank you for shopping with PokeBulk SA! If you have any questions about your order, contact us at <strong>enquiries@pokebulk.co.za</strong> or call <strong>074 488 6919</strong>.</p>
  </div>
  <div style="background:#f0f0f0;padding:14px 28px;text-align:center;font-size:11px;color:#888">
    Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. 2024/615040/07 &nbsp;|&nbsp; 4 Heloise Street, Birchleigh North, Kempton Park, 1618
  </div>
</div>
</body></html>'''

    payload = _json.dumps({
        "from": "PokeBulk SA <orders@updates.pokebulk.co.za>",
        "to": [customer_email],
        "subject": f"PokeBulk SA — Invoice {invoice_num}",
        "html": html_body,
    }).encode('utf-8')
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        return HttpResponse(
            f'<script>alert("Invoice sent to {customer_email}");window.history.back();</script>',
            content_type='text/html'
        )
    except Exception as e:
        return HttpResponse(f'Failed to send: {e}', status=500)


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
            <td style="padding:5px 8px;font-size:12px">{i}</td>
            <td style="padding:5px 8px;font-size:12px">{set_name} [{set_code}]</td>
            <td style="padding:5px 8px;font-size:12px">#{num}</td>
            <td style="padding:5px 8px;font-size:12px">{name}</td>
            <td style="padding:5px 8px;font-size:12px">{rarity}</td>
            <td style="padding:5px 8px;font-size:12px">{var}</td>
            <td style="padding:5px 8px;font-size:12px;text-align:center">{item.quantity}</td>
            <td style="padding:5px 8px;font-size:12px;text-align:right">R {item.price_at_purchase:.2f}</td>
            <td style="padding:5px 8px;font-size:12px;text-align:right">R {float(item.price_at_purchase) * item.quantity:.2f}</td>
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

    waybill_row = f'<tr><td style="color:#555;padding:3px 0;font-size:12px">Waybill</td><td style="padding:3px 0;font-size:12px;font-weight:bold">{order.waybill_number}</td></tr>' if order.waybill_number else ''
    eft_notice = '<div style="background:#f5f5f5;border-radius:6px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#333"><strong>Banking details:</strong> Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Nedbank Current &nbsp;|&nbsp; Branch: 198765 &nbsp;|&nbsp; Acc: 1301474037</div>' if order.payment_method in ['eft', 'coc'] else ''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{invoice_num} - PokeBulk SA</title>
<style>* {{ box-sizing:border-box;margin:0;padding:0 }} body {{ font-family:Arial,sans-serif;padding:24px;color:#222;font-size:13px }} @media print {{ .no-print {{ display:none !important }} @page {{ margin:12mm;size:A4 }} }} table {{ border-collapse:collapse }} th {{ background:#f0f0f0;font-size:11px;font-weight:bold;padding:7px 8px;text-align:left;border-bottom:2px solid #ddd }}</style>
</head><body>
<div class="no-print" style="margin-bottom:16px;display:flex;gap:8px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;cursor:pointer;font-weight:bold">Print Invoice</button>
  <button onclick="window.close()" style="background:#eee;color:#333;border:none;padding:9px 16px;border-radius:6px;font-size:13px;cursor:pointer">Close</button>
</div>
<div style="display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:14px;border-bottom:3px solid #ff6b35;margin-bottom:18px">
  <div><div style="font-size:17px;font-weight:bold;color:#ff6b35">Poke Bulk SA <span style="color:#222">(Pty) Ltd</span></div>
  <div style="font-size:11px;color:#555;line-height:1.7;margin-top:2px">Reg. No: 2024/615040/07<br>4 Heloise Street, Birchleigh North, Kempton Park, 1618<br>Tel: 074 488 6919 &nbsp;|&nbsp; enquiries@pokebulk.co.za</div></div>
  <div style="text-align:right"><div style="font-size:20px;font-weight:bold;color:#333">INVOICE</div>
  <div style="font-size:13px;margin-top:4px"><strong>{invoice_num}</strong></div>
  <div style="font-size:12px;color:#555;margin-top:2px">{invoice_date}</div>
  <div style="margin-top:6px;font-size:12px;color:#555">Status: <strong>{order.get_status_display()}</strong></div></div>
</div>
{eft_notice}
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:18px">
  <div style="background:#f9f9f9;border-radius:6px;padding:10px 12px">
    <div style="font-size:10px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Buyer</div>
    <div style="font-weight:bold;font-size:13px">{customer_name}</div>
    <div style="font-size:12px;color:#555;margin-top:2px;line-height:1.6">{customer_email}<br>{phone}</div>
  </div>
  <div style="background:#f9f9f9;border-radius:6px;padding:10px 12px">
    <div style="font-size:10px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Delivery</div>
    <div style="font-weight:bold;font-size:13px">{delivery_label}</div>
    <div style="font-size:12px;color:#555;margin-top:2px;line-height:1.6">{delivery_detail}</div>
  </div>
  <div style="background:#f9f9f9;border-radius:6px;padding:10px 12px">
    <div style="font-size:10px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Payment</div>
    <table style="width:100%;font-size:12px">
      <tr><td style="color:#555;padding:2px 0">Method</td><td style="font-weight:bold;padding:2px 0;text-align:right">{order.get_payment_method_display()}</td></tr>
      {waybill_row}
    </table>
  </div>
</div>
<table style="width:100%;margin-bottom:16px">
  <thead><tr><th width="30">#</th><th>Set</th><th width="60">Card #</th><th>Card name</th><th width="100">Rarity</th><th width="55">Variant</th><th width="40" style="text-align:center">Qty</th><th width="75" style="text-align:right">Unit</th><th width="80" style="text-align:right">Total</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<div style="display:flex;justify-content:flex-end;margin-bottom:20px">
  <table style="width:260px">
    <tr><td style="padding:5px 8px;color:#555">Subtotal ({item_count} items)</td><td style="padding:5px 8px;text-align:right">R {subtotal:.2f}</td></tr>
    <tr><td style="padding:5px 8px;color:#555">Shipping</td><td style="padding:5px 8px;text-align:right">{"FREE" if shipping == 0 else f"R {shipping:.2f}"}</td></tr>
    <tr style="font-weight:bold;font-size:15px;border-top:2px solid #ff6b35"><td style="padding:8px 8px">TOTAL</td><td style="padding:8px 8px;text-align:right;color:#ff6b35">R {total:.2f}</td></tr>
  </table>
</div>
<div style="border-top:1px solid #eee;padding-top:12px;font-size:11px;color:#888;text-align:center">
  Thank you for your order! &nbsp;|&nbsp; Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. No: 2024/615040/07 &nbsp;|&nbsp; enquiries@pokebulk.co.za
</div>
</body></html>'''
    return HttpResponse(html, content_type='text/html; charset=utf-8')
