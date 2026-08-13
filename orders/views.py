import logging
import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.html import strip_tags
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import PokemonProduct
from .models import Cart, CartItem, Order, OrderItem, OrderTracking, ManualInvoice, community_discount_percent
from .serializers import (
    CartSerializer, CartItemSerializer, OrderSerializer,
    OrderStatusUpdateSerializer, AdminOrderListSerializer,
    ManualInvoiceListSerializer,
)

logger = logging.getLogger(__name__)
# Some products (mainly ASC-era stamped Reverse Holos) carry their physical
# stamp/pattern as a trailing parenthetical on the product name, e.g.
# "Team Rocket's Spidops (Energy Symbol Pattern)" vs "...(Team Rocket)" vs
# "...(Poke Ball)". These are visually distinct physical prints that all
# share variant_override='RH', so a plain "Reverse Holo" badge alone can't
# tell them apart when packing. These helpers pull the pattern out so it
# can be shown as its own badge/label, and return the cleaned display name
# without the suffix.
_PATTERN_SUFFIX_RE = re.compile(r'\s*\(([^)]+)\)\s*$')

# WHITELIST ONLY. Confirmed via scan_name_pattern_suffixes.py (2026-07-26)
# against the live catalog. A trailing "(...)" is extremely common in card
# names for reasons that are NOT a stamp/pattern -- rarity (Secret, Full
# Art), card mechanics (Delta Species, Alpha/Omega, Attack Forme), event
# context (Prerelease, World Championships 2019), disambiguating numbers
# ((28), (H30)), letters (Unown (Y)), etc. Stripping those would corrupt
# the displayed card name and mislabel the variant. Only strip a suffix
# if it exactly matches (case-insensitive) one of these known physical
# stamp/pattern names -- confirmed sets: ASC (Energy Symbol/ball/Team
# Rocket patterns on RH cards), WHT/BLK/PRE (Poke/Master Ball Pattern on
# H cards), and various Cosmos/Cosmo Holo(foil) sets.
_KNOWN_NAME_PATTERNS = {
    'energy symbol pattern': 'Energy Symbol Pattern',
    'team rocket': 'Team Rocket',
    'poke ball': 'Poke Ball',
    'master ball': 'Master Ball',
    'love ball': 'Love Ball',
    'friend ball': 'Friend Ball',
    'quick ball': 'Quick Ball',
    'dusk ball': 'Dusk Ball',
    'poke ball pattern': 'Poke Ball Pattern',
    'master ball pattern': 'Master Ball Pattern',
    'cosmos holo': 'Cosmos Holo',
    'cosmo holo': 'Cosmo Holo',
    'cosmos holofoil': 'Cosmos Holofoil',
    'cosmo holofoil': 'Cosmo Holofoil',
}

_PATTERN_BADGE_COLORS = {
    'Energy Symbol Pattern': '#e1f5fe;color:#01579b',
    'Team Rocket': '#37474f;color:#ffffff',
    'Poke Ball': '#ffebee;color:#c62828',
    'Master Ball': '#ede7f6;color:#4527a0',
    'Love Ball': '#fce4ec;color:#ad1457',
    'Friend Ball': '#e8f5e9;color:#2e7d32',
    'Quick Ball': '#fff3e0;color:#e65100',
    'Dusk Ball': '#efebe9;color:#4e342e',
    'Poke Ball Pattern': '#ffebee;color:#c62828',
    'Master Ball Pattern': '#ede7f6;color:#4527a0',
    'Cosmos Holo': '#e0f7fa;color:#006064',
    'Cosmo Holo': '#e0f7fa;color:#006064',
    'Cosmos Holofoil': '#e0f7fa;color:#006064',
    'Cosmo Holofoil': '#e0f7fa;color:#006064',
}

# Short labels so the pattern badge doesn't blow up the row -- full name
# is still in the CSS title="" tooltip on hover/inspection.
_PATTERN_BADGE_SHORT = {
    'Energy Symbol Pattern': 'Energy Symbol',
    'Team Rocket': 'Team Rocket',
    'Poke Ball': 'Poke Ball',
    'Master Ball': 'Master Ball',
    'Love Ball': 'Love Ball',
    'Friend Ball': 'Friend Ball',
    'Quick Ball': 'Quick Ball',
    'Dusk Ball': 'Dusk Ball',
    'Poke Ball Pattern': 'Poke Ball',
    'Master Ball Pattern': 'Master Ball',
    'Cosmos Holo': 'Cosmos',
    'Cosmo Holo': 'Cosmos',
    'Cosmos Holofoil': 'Cosmos',
    'Cosmo Holofoil': 'Cosmos',
}


def _split_name_pattern(name):
    match = _PATTERN_SUFFIX_RE.search(name or '')
    if not match:
        return name, None
    raw = match.group(1).strip()
    canonical = _KNOWN_NAME_PATTERNS.get(raw.lower())
    if not canonical:
        # Not a known stamp/pattern -- leave the name untouched.
        return name, None
    display_name = name[:match.start()].strip()
    return display_name, canonical


def _pattern_badge_color(pattern):
    return _PATTERN_BADGE_COLORS.get(pattern, '#e8e8e8;color:#333')


class CartView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        Cart.objects.get_or_create(user=self.request.user)
        # The nested PokemonProductSerializer pulls in category, card_set (+ its era),
        # and pokemon_types for every item. Without prefetching those specifically,
        # each cart item fires 3-4 extra queries -- this is what was causing
        # WORKER TIMEOUT / 500s on /api/cart/ for carts with several items.
        return Cart.objects.prefetch_related(
            Prefetch(
                'items',
                queryset=CartItem.objects.select_related(
                    'product__category', 'product__card_set__era'
                ).prefetch_related('product__pokemon_types')
            )
        ).get(user=self.request.user)


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
        subtotal = sum(item.subtotal for item in items)
        payment_method = request.data.get('payment_method', 'payfast')
        shipping_method = request.data.get('shipping_method', 'pudo_locker')
        is_eft = payment_method == 'eft'
        is_coc = shipping_method == 'collection'

        pudo_locker_name = request.data.get('pudo_locker_name', '')
        pudo_locker_address = request.data.get('pudo_locker_address', '')
        # Michael, 2026-08-02: 3 orders came through with a Pudo locker/kiosk
        # method selected but no locker name/address attached -- nothing to
        # actually book the courier against. Reject the order at checkout
        # instead of letting it through silently. Only the locker-to-*
        # methods need pudo_locker_name/address -- pudo_door and postnet
        # deliver to a street address instead (frontend's own needsLocker
        # list), so those two are deliberately excluded here.
        PUDO_LOCKER_METHODS = {'pudo_locker', 'pudo_kiosk', 'pudo_medium'}
        if shipping_method in PUDO_LOCKER_METHODS and (not pudo_locker_name or not pudo_locker_address):
            return Response(
                {'error': 'Please select a Pudo locker/kiosk before placing this order.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            shipping_cost = Decimal(str(request.data.get('shipping_cost', 0) or 0))
        except Exception:
            shipping_cost = Decimal('0')

        # Community discount (2026-08-11) -- 5% off for anyone with a public
        # community profile. Snapshotted onto the order (see Order model
        # docstring) rather than only ever computed live, so the invoice
        # keeps showing what was actually charged even if the rate or the
        # customer's opt-in status changes later.
        discount_percent = community_discount_percent(request.user)
        discount_amount = (
            (subtotal * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
            if discount_percent else Decimal('0.00')
        )

        total = subtotal - discount_amount + shipping_cost

        order = Order.objects.create(
            user=request.user,
            total_price=total,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            status='pending_eft' if is_eft else ('awaiting_payment' if payment_method == 'payfast' else 'pending'),
            payment_method='coc' if is_coc else payment_method,
            shipping_method=shipping_method,
            shipping_cost=shipping_cost,
            delivery_method='collection' if is_coc else 'courier',
            delivery_address_line1=request.data.get('address_line1', ''),
            delivery_address_line2=request.data.get('address_line2', ''),
            delivery_city=request.data.get('city', ''),
            delivery_province=request.data.get('province', ''),
            delivery_postal_code=request.data.get('postal_code', ''),
            pudo_locker_name=pudo_locker_name,
            pudo_locker_address=pudo_locker_address,
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
            status=order.status,
            note='Order received successfully.',
        )

        # Automated order-confirmation email -- fires only after the DB
        # transaction actually commits (transaction.on_commit below), NOT
        # inline here. Uses the exact same _build_invoice_html the manual
        # "Email Order" admin button already uses, so there's one source of
        # truth for what an invoice looks like.
        #
        # Michael, 2026-08-02: this used to run inline, right here, before
        # the view returned -- still inside the @transaction.atomic block.
        # If literally anything after the send raised (e.g. a hiccup while
        # serializing the response two lines below), Django rolled back the
        # whole transaction -- order, order items, stock decrement, cart
        # clear, all of it -- but the email had already gone out
        # irreversibly, since sending mail isn't part of the DB transaction
        # and can't be undone. Customer got a confirmation email for an
        # order that no longer existed in the DB, with their cart/Pile still
        # full and nothing to show for it. transaction.on_commit() defers
        # the send until Django confirms the transaction actually committed
        # -- if it rolls back for any reason, on_commit's callback is simply
        # discarded and no email goes out. Failures inside the send itself
        # are still caught and logged, never raised.
        def _send_confirmation_email():
            try:
                html, invoice_num, customer_email = _build_invoice_html(order, show_controls=False)
                if customer_email:
                    subject = f'Your PokeBulk SA Order Confirmation — Order #{order.id} ({invoice_num})'
                    text_body = strip_tags(html)
                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        to=[customer_email],
                        bcc=['enquiries@pokebulk.co.za'],
                    )
                    email.attach_alternative(html, 'text/html')
                    email.send(fail_silently=False)
                    logger.info(
                        "Order confirmation email sent for order_id=%s to=%s",
                        order.id, customer_email,
                    )
                else:
                    logger.warning(
                        "Order #%s placed but user_id=%s has no email on file -- confirmation not sent.",
                        order.id, order.user_id,
                    )
            except Exception:
                logger.exception(
                    "Failed to send order confirmation email for order_id=%s", order.id,
                )

        transaction.on_commit(_send_confirmation_email)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related(
            Prefetch(
                'items',
                queryset=OrderItem.objects.select_related(
                    'product__category', 'product__card_set__era'
                ).prefetch_related('product__pokemon_types')
            ),
            'tracking',
        )


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related(
            Prefetch(
                'items',
                queryset=OrderItem.objects.select_related(
                    'product__category', 'product__card_set__era'
                ).prefetch_related('product__pokemon_types')
            ),
            'tracking',
        )


class OrderStatusUpdateView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, pk):
        try:
            # PERF FIX 2026-08-12 (Michael: "everytime i retry, it sends
            # email again!", seen on order #135 with 274 items): a bare
            # Order.objects.get() here meant the OrderSerializer(order).data
            # call at the bottom of this view triggered one extra query PER
            # item just to fetch its product -- 274+ queries for a big
            # order. Slow enough on a big order to plausibly blow past a
            # gateway timeout, which drops the client's connection before it
            # ever sees the (eventually successful) response -- the save
            # looks "failed" in the browser even though it committed and the
            # status-update email already went out, so every retry sends
            # another one. select_related/prefetch_related here cuts that
            # down to a handful of queries regardless of order size.
            order = Order.objects.select_related('user').prefetch_related(
                Prefetch('items', queryset=OrderItem.objects.select_related('product')),
                'tracking',
            ).get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        note = request.data.get('note', '')
        waybill = request.data.get('waybill_number', '')
        courier_name = request.data.get('courier_name', '')
        courier_url = request.data.get('courier_tracking_url', '')

        # status is now optional -- a request can be payment-confirmation-only
        # (see below) with no status change at all.
        if new_status is not None and new_status not in dict(Order.STATUS_CHOICES):
            return Response({'error': f'Invalid status: {new_status}'}, status=status.HTTP_400_BAD_REQUEST)

        if new_status is not None:
            order.status = new_status
        if waybill:
            order.waybill_number = waybill
        if courier_name:
            order.courier_name = courier_name
        if courier_url:
            order.courier_tracking_url = courier_url

        # Payment confirmation (2026-08-12): Michael, "only feature to add,
        # is payment confirmation, Cash - EFT - Payfast" -- EFT/Cash are
        # manual tick boxes, matching OrderAdmin's own eft_confirmed/
        # cash_confirmed fields exactly. PayFast is normally confirmed
        # automatically by the ITN webhook writing stripe_payment_intent,
        # but that field's exposed here too as an editable reference for
        # the rare case staff need to correct it by hand -- the same
        # capability OrderAdmin's collapsed "Technical" fieldset already
        # allows, just surfaced in the new staff dashboard too. Checked
        # with 'in' (not truthiness) so explicitly un-ticking a
        # confirmation (False) is distinguishable from "wasn't sent".
        if 'eft_confirmed' in request.data:
            order.eft_confirmed = bool(request.data.get('eft_confirmed'))
        if 'cash_confirmed' in request.data:
            order.cash_confirmed = bool(request.data.get('cash_confirmed'))
        if 'stripe_payment_intent' in request.data:
            order.stripe_payment_intent = request.data.get('stripe_payment_intent') or ''

        # Stashed as plain attributes (never saved to the DB) so
        # orders/signals.py's post_save receiver can build a richer
        # OrderTracking entry -- real note/waybill/created_by -- instead of
        # the bare one it used to create alone.
        #
        # Found while wiring this up: now that the signal actually fires
        # (orders/apps.py's ready() fix, earlier today), this view's OWN
        # unconditional OrderTracking.objects.create() call that used to
        # sit right after order.save() would have started producing a
        # DUPLICATE tracking row -- plus a second status-update email to
        # the customer -- every single time, since the signal already
        # creates one too whenever status changes. That call is removed
        # below entirely; the signal is now the one and only place a
        # status change ever creates a tracking row or sends the update
        # email, no matter whether the change came from this view, the
        # Django admin form, or anywhere else that calls order.save().
        order._tracking_note = note
        order._tracking_waybill = waybill
        order._tracking_created_by = request.user

        order.save()

        return Response(OrderSerializer(order).data)


class AdminOrderListView(generics.ListAPIView):
    """Feeds the staff Orders dashboard's changelist-style table (2026-08-12).
    Deliberately lean -- no nested item/product data, just what a
    changelist row needs, plus status/paid/search filters mirroring
    OrderAdmin's own list_filter/search_fields/PaidFilter so the new
    dashboard and Django admin stay behaviourally consistent."""
    serializer_class = AdminOrderListSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = Order.objects.select_related('user').prefetch_related('items')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        else:
            # Same default as OrderAdmin's changelist -- open orders only,
            # unless a status is explicitly requested (including 'cancelled'
            # or 'invoiced' themselves).
            qs = qs.exclude(status__in=['cancelled', 'invoiced'])

        paid_filter = self.request.query_params.get('paid')
        if paid_filter in ('yes', 'no'):
            paid_q = (
                (Q(payment_method='payfast') & ~Q(stripe_payment_intent=''))
                | Q(payment_method='eft', eft_confirmed=True)
                | Q(payment_method='coc', cash_confirmed=True)
            )
            qs = qs.filter(paid_q) if paid_filter == 'yes' else qs.exclude(paid_q)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(user__username__icontains=search) | Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search)
                | Q(waybill_number__icontains=search)
            )

        return qs.order_by('-created_at')


class AdminManualInvoiceListView(generics.ListAPIView):
    """Manual Invoice's first REST API (2026-08-12) -- read-only, feeds the
    staff dashboard's Manual Invoices tab. Creating/editing invoices still
    goes through the existing POS screen (admin.py's pos_view), linked out
    to rather than rebuilt here."""
    serializer_class = ManualInvoiceListSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = ManualInvoice.objects.select_related('user').prefetch_related('items')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        payment_filter = self.request.query_params.get('payment_received')
        if payment_filter in ('true', 'false'):
            qs = qs.filter(payment_received=(payment_filter == 'true'))

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(customer_name__icontains=search) | Q(customer_email__icontains=search)
                | Q(invoice_number__icontains=search)
                # 2026-08-12: also matches by the linked site account, so
                # searching a username/account email finds invoices where
                # the free-text customer_name/email don't happen to match.
                | Q(user__username__icontains=search) | Q(user__email__icontains=search)
            )

        return qs.order_by('-created_at')


class AdminManualInvoiceStatusUpdateView(APIView):
    """PATCH-only status update for a Manual Invoice (2026-08-12) -- Michael:
    "Manual Invoicing can we do a status too?" Mirrors OrderStatusUpdateView's
    shape (status + optional payment fields in one PATCH) but much simpler:
    no waybill/courier/tracking, no OrderTracking-equivalent history table.
    payment_received/payment_method can be updated in the same call, but
    ManualInvoice.save() already auto-syncs payment_received once status
    reaches 'payment_confirmed' or later, so that's rarely needed separately."""
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            invoice = ManualInvoice.objects.get(pk=pk)
        except ManualInvoice.DoesNotExist:
            return Response({'error': 'Manual invoice not found'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if new_status is not None:
            if new_status not in dict(ManualInvoice.STATUS_CHOICES):
                return Response({'error': f'Invalid status: {new_status}'}, status=status.HTTP_400_BAD_REQUEST)
            invoice.status = new_status

        if 'payment_received' in request.data:
            invoice.payment_received = bool(request.data.get('payment_received'))
        if 'payment_method' in request.data:
            method = request.data.get('payment_method') or ''
            if method and method not in dict(ManualInvoice.PAYMENT_METHOD_CHOICES):
                return Response({'error': f'Invalid payment_method: {method}'}, status=status.HTTP_400_BAD_REQUEST)
            invoice.payment_method = method

        invoice.save()
        return Response(ManualInvoiceListSerializer(invoice).data)


class AdminCustomerSalesSummaryView(APIView):
    """Staff-only per-customer sales totals (2026-08-12) -- Michael: "Can we
    add individual customer totaling? Show active orders and their total and
    then customers total sales, must include manual invoices." Feeds the
    customer panel on /staff/checklists, right alongside the checklist
    have/needed view already there.

    Matched on the linked ManualInvoice.user account (reliable) OR a
    matching email (covers older/walk-in invoices from before account
    linking existed) -- same join key Michael already uses himself when a
    repeat customer calls in. Every total here excludes 'cancelled' (both
    Order and ManualInvoice), matching how the Store Overview page already
    defines "sales" so the two pages agree.

    2026-08-12 follow-up -- Michael: "not pulling in the manual invoices?"
    -- the totals DID already include manual invoices, but the "active"
    list itself was Order-only, so an in-progress manual invoice was
    invisible even though it was silently baked into the total. active_*
    below is now a single combined list of both types, sorted together.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, user_id):
        from django.contrib.auth import get_user_model
        from django.db.models import Sum
        User = get_user_model()
        try:
            customer = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        orders_qs = Order.objects.filter(user=customer)
        order_sales_total = orders_qs.exclude(status='cancelled').aggregate(t=Sum('total_price'))['t'] or Decimal('0.00')

        email_q = Q(customer_email__iexact=customer.email) if customer.email else Q(pk__in=[])
        manual_invoices_qs = ManualInvoice.objects.filter(Q(user=customer) | email_q).exclude(status='cancelled')
        manual_invoice_total = sum((mi.total for mi in manual_invoices_qs), Decimal('0.00'))

        # "Active" = not yet finished either way. Orders: same exclude set
        # AdminOrderListView already defaults to. Manual Invoice: excludes
        # its own equivalent 'finished' states (complete/cancelled) --
        # 'cancelled' is already excluded on manual_invoices_qs above.
        active_items = [{
            'type': 'order',
            'id': o.id,
            'label': f'#{o.id}',
            'status': o.status,
            'status_display': o.get_status_display(),
            'total': str(o.total_price),
            'created_at': o.created_at,
        } for o in orders_qs.exclude(status__in=['cancelled', 'invoiced'])]

        active_items += [{
            'type': 'manual_invoice',
            'id': mi.id,
            'label': mi.invoice_number,
            'status': mi.status,
            'status_display': mi.get_status_display(),
            'total': str(mi.total),
            'created_at': mi.created_at,
        } for mi in manual_invoices_qs.exclude(status='complete')]

        active_items.sort(key=lambda x: x['created_at'], reverse=True)
        active_total = sum((Decimal(x['total']) for x in active_items), Decimal('0.00'))

        return Response({
            'active_orders': active_items,
            'active_orders_total': str(active_total),
            'order_sales_total': str(order_sales_total),
            'manual_invoice_total': str(manual_invoice_total),
            'manual_invoice_count': manual_invoices_qs.count(),
            'total_sales': str(order_sales_total + manual_invoice_total),
        })


@staff_member_required
def print_order(request, order_id):
    from django.utils import timezone
    from itertools import groupby

    VARIANT_LABEL_FULL = {
        'N': 'Normal', 'H': 'Holo', 'RH': 'Reverse Holo',
        'PB': 'Poke Ball', 'MB': 'Master Ball', 'LB': 'Love Ball',
        'FB': 'Friend Ball', 'QB': 'Quick Ball', 'UB': 'Ultra Ball',
        'DB': 'Dusk Ball', 'TR': 'Team Rocket', 'SE': 'Secret',
        'PBP': 'PB Pattern', 'MBP': 'MB Pattern',
        'CC': 'Code Card', 'TT': 'Trick or Trade',
    }

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
            var_code = p.variant_override or 'N'
            name, pattern = _split_name_pattern(p.name)
        else:
            num = '--'
            var_code = '?'
            name = item.product_name or item.product_sku or 'Unknown card'
            pattern = None
        return num, name, var_code, pattern

    sets_html = ''
    for (set_name, set_code), group in groupby(sorted(items, key=get_set_key), key=get_set_key):
        cards = list(group)
        line_count = len(cards)
        total_qty = sum(item.quantity for item in cards)
        rows = ''
        for i, item in enumerate(cards, 1):
            num, name, var_code, pattern = get_item_display(item)
            var_label = VARIANT_LABEL_FULL.get(var_code, var_code or 'Unknown')
            var_colors = {
                'N': '#e8e8e8;color:#333', 'H': '#fff3cd;color:#856404', 'RH': '#e8e4ff;color:#4c3d99',
                'PB': '#fce4ec;color:#ad1457', 'MB': '#ede7f6;color:#5e35b1', 'LB': '#fff0f3;color:#c2185b',
                'FB': '#e8f5e9;color:#2e7d32', 'QB': '#fff3e0;color:#e65100', 'UB': '#e3f2fd;color:#1565c0',
                'DB': '#efebe9;color:#4e342e', 'TR': '#eceff1;color:#37474f', 'SE': '#fffde7;color:#f57f17',
                'PBP': '#fce4ec;color:#ad1457', 'MBP': '#ede7f6;color:#5e35b1',
                'CC': '#f5f5f5;color:#616161', 'TT': '#fce4ec;color:#880e4f',
            }
            var_style = var_colors.get(var_code, '#e8e8e8;color:#333')
            variant_cell = f'<div style="display:flex;gap:3px;align-items:center;white-space:nowrap"><span style="background:{var_style};padding:1px 5px;border-radius:8px;font-size:9px;font-weight:bold">{var_label}</span>'
            if pattern:
                pattern_style = _pattern_badge_color(pattern)
                pattern_short = _PATTERN_BADGE_SHORT.get(pattern, pattern)
                variant_cell += f'<span title="{pattern}" style="background:{pattern_style};padding:1px 5px;border-radius:8px;font-size:9px;font-weight:bold">{pattern_short}</span>'
            variant_cell += '</div>'
            rows += f'''<tr>
              <td>{i}</td><td>{num}</td><td>{name}</td>
              <td>{variant_cell}</td>
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
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="130">Variant</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="40">Qty</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="90">Price</th>
              <th style="text-align:left;padding:2px 8px;font-size:10px;border-bottom:1px solid #ccc" width="30">Done</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table></div>'''

    if order.delivery_method == 'collection':
        delivery_info = 'LOCAL COLLECTION - Unit 4, Sunkist Village, 11 Heliose Street, Birchleigh North, Kempton Park'
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
  <tr style="font-weight:bold;background:#fff3e8"><td colspan="5" style="text-align:right;padding:4px 8px">Total Cards to Pack</td><td style="padding:4px 8px;color:#ff6b35">{item_count}</td><td></td></tr>
  <tr style="font-weight:bold;background:#f9f9f9"><td colspan="5" style="text-align:right;padding:4px 8px">Subtotal</td><td style="padding:4px 8px">R {subtotal:.2f}</td><td></td></tr>
  {f'<tr style="font-weight:bold;background:#f9f9f9;color:#2e7d32"><td colspan="5" style="text-align:right;padding:4px 8px">Community discount ({order.discount_percent:.0f}%)</td><td style="padding:4px 8px">-R {order.discount_amount:.2f}</td><td></td></tr>' if order.discount_amount else ''}
  <tr style="font-weight:bold;background:#f9f9f9"><td colspan="5" style="text-align:right;padding:4px 8px">Shipping</td><td style="padding:4px 8px">R {shipping:.2f}</td><td></td></tr>
  <tr style="font-weight:bold;font-size:14px"><td colspan="5" style="text-align:right;padding:4px 8px">TOTAL</td><td style="padding:4px 8px;color:#ff6b35">R {order.total_price:.2f}</td><td></td></tr>
</table>
<div style="margin-top:10px;border-top:1px solid #ccc;padding-top:6px;font-size:10px;color:#666">
  Printed: {printed_at} | PokeBulk SA - Unit 4, Sunkist Village, 11 Heliose Street, Birchleigh North, Kempton Park | enquiries@pokebulk.co.za
</div>
</body></html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')



def _build_invoice_html(order, show_controls=True):
    """Builds the full invoice HTML for an order. Shared by the browser
    print view and the email-send view. show_controls=False strips the
    Print/Close buttons (no point emailing those to a customer)."""
    VARIANT_LABEL_FULL = {
        'N': 'Normal', 'H': 'Holo', 'RH': 'Reverse Holo',
        'PB': 'Poke Ball', 'MB': 'Master Ball', 'LB': 'Love Ball',
        'FB': 'Friend Ball', 'QB': 'Quick Ball', 'UB': 'Ultra Ball',
        'DB': 'Dusk Ball', 'TR': 'Team Rocket', 'SE': 'Secret',
        'PBP': 'PB Pattern', 'MBP': 'MB Pattern',
        'CC': 'Code Card', 'TT': 'Trick or Trade',
    }
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
            var_code = p.variant_override or 'N'
            var_base = VARIANT_LABEL_FULL.get(var_code, var_code)
            set_name = p.card_set.name if p.card_set else '-'
            set_code = p.card_set.code if p.card_set else ''
            rarity = (p.rarity or '').replace('_', ' ').title()
            name, pattern = _split_name_pattern(p.name)
            if pattern:
                pattern_short = _PATTERN_BADGE_SHORT.get(pattern, pattern)
                var = f'{var_base} ({pattern_short})'
            else:
                var = var_base
        else:
            num = '--'; var = '?'; set_name = '-'; set_code = ''; rarity = ''; name = item.product_name or item.product_sku or 'Unknown card'
        rows += f'''<tr style="border-bottom:1px solid #eee">
            <td style="padding:1px 5px;font-size:9px">{i}</td>
            <td style="padding:1px 5px;font-size:9px;white-space:nowrap" title="{set_name}"><strong>{set_code}</strong></td>
            <td style="padding:1px 5px;font-size:9px;white-space:nowrap">#{num}</td>
            <td style="padding:1px 5px;font-size:9px">{name}</td>
            <td style="padding:1px 5px;font-size:9px;white-space:nowrap">{rarity}</td>
            <td style="padding:1px 5px;font-size:9px;white-space:nowrap">{var}</td>
            <td style="padding:1px 5px;font-size:9px;text-align:center">{item.quantity}</td>
            <td style="padding:1px 5px;font-size:9px;text-align:right;white-space:nowrap">R {item.price_at_purchase:.2f}</td>
            <td style="padding:1px 5px;font-size:9px;text-align:right;white-space:nowrap">R {float(item.price_at_purchase) * item.quantity:.2f}</td>
        </tr>'''

    subtotal = sum(float(item.price_at_purchase) * item.quantity for item in items)
    shipping = float(order.shipping_cost or 0)
    discount_amount = float(order.discount_amount or 0)
    total = subtotal - discount_amount + shipping
    item_count = sum(i.quantity for i in items)
    invoice_date = order.created_at.strftime('%d-%m-%Y')
    invoice_num = f'INV {order.id:08d}'
    customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.username
    customer_email = order.user.email
    phone = getattr(order.user, 'phone_number', '') or ''

    if order.delivery_method == 'collection':
        delivery_label = 'Local Collection'
        delivery_detail = 'Unit 4, Sunkist Village, 11 Heliose Street, Birchleigh North, Kempton Park'
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

    invoice_note_block = ''
    if order.invoice_note:
        note_text = order.invoice_note.replace('\n', '<br>')
        invoice_note_block = f'''<div style="background:#fff7f2;border-left:3px solid #ff6b35;border-radius:6px;padding:6px 10px;margin-bottom:12px">
      <div style="font-size:9px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:3px">Note</div>
      <div style="font-size:11px;color:#333;line-height:1.3">{note_text}</div>
    </div>'''

    controls_html = '''<div class="no-print" style="margin-bottom:16px;display:flex;gap:8px">
  <button onclick="window.print()" style="background:#ff6b35;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;cursor:pointer;font-weight:bold">Print Invoice</button>
  <button onclick="window.close()" style="background:#eee;color:#333;border:none;padding:9px 16px;border-radius:6px;font-size:13px;cursor:pointer">Close</button>
</div>''' if show_controls else ''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{invoice_num} - PokeBulk SA</title>
<style>* {{ box-sizing:border-box;margin:0;padding:0 }} body {{ font-family:Arial,sans-serif;padding:10px;color:#222;font-size:10px;line-height:1.15 }} @media print {{ .no-print {{ display:none !important }} @page {{ margin:7mm;size:A4 }} }} table {{ border-collapse:collapse }} th {{ background:#f0f0f0;font-size:9px;font-weight:bold;padding:2px 5px;text-align:left;border-bottom:2px solid #ddd }}</style>
</head><body>
{controls_html}
<div style="display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:6px;border-bottom:3px solid #ff6b35;margin-bottom:8px">
  <div><div style="font-size:15px;font-weight:bold;color:#ff6b35">Poke Bulk SA <span style="color:#222">(Pty) Ltd</span></div>
  <div style="font-size:9px;color:#555;line-height:1.25;margin-top:2px">Reg. No: 2024/615040/07<br>Unit 4, Sunkist Village, 11 Heliose Street, Birchleigh North, Kempton Park, 1618<br>Tel: 074 488 6919 &nbsp;|&nbsp; enquiries@pokebulk.co.za</div></div>
  <div style="text-align:right"><div style="font-size:16px;font-weight:bold;color:#333">INVOICE</div>
  <div style="font-size:11px;margin-top:2px"><strong>{invoice_num}</strong></div>
  <div style="font-size:9px;color:#555;margin-top:1px">{invoice_date}</div>
  <div style="margin-top:3px;font-size:9px;color:#555">Status: <strong>{order.get_status_display()}</strong></div></div>
</div>
{eft_notice}
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px">
  <div style="background:#f9f9f9;border-radius:5px;padding:4px 8px">
    <div style="font-size:8px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px">Buyer</div>
    <div style="font-weight:bold;font-size:10px">{customer_name}</div>
    <div style="font-size:9px;color:#555;margin-top:1px;line-height:1.2">{customer_email}<br>{phone}</div>
  </div>
  <div style="background:#f9f9f9;border-radius:5px;padding:4px 8px">
    <div style="font-size:8px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px">Delivery</div>
    <div style="font-weight:bold;font-size:10px">{delivery_label}</div>
    <div style="font-size:9px;color:#555;margin-top:1px;line-height:1.2">{delivery_detail}</div>
  </div>
  <div style="background:#f9f9f9;border-radius:5px;padding:4px 8px">
    <div style="font-size:8px;color:#888;font-weight:bold;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px">Payment</div>
    <table style="width:100%;font-size:9px">
      <tr><td style="color:#555;padding:1px 0">Method</td><td style="font-weight:bold;padding:1px 0;text-align:right">{order.get_payment_method_display()}</td></tr>
      {waybill_row}
    </table>
  </div>
</div>
{invoice_note_block}
<table style="width:100%;margin-bottom:8px">
  <thead><tr><th width="22">#</th><th width="38">Set</th><th width="55">Card #</th><th>Card name</th><th width="65">Rarity</th><th width="115">Variant</th><th width="30" style="text-align:center">Qty</th><th width="55" style="text-align:right">Unit</th><th width="60" style="text-align:right">Total</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<div style="display:flex;justify-content:flex-end;margin-bottom:12px">
  <table style="width:260px">
    <tr><td style="padding:2px 8px;color:#555">Subtotal ({item_count} items)</td><td style="padding:2px 8px;text-align:right">R {subtotal:.2f}</td></tr>
    {f'<tr><td style="padding:2px 8px;color:#2e7d32">Community discount ({order.discount_percent:.0f}%)</td><td style="padding:2px 8px;text-align:right;color:#2e7d32">-R {discount_amount:.2f}</td></tr>' if discount_amount else ''}
    <tr><td style="padding:2px 8px;color:#555">Shipping</td><td style="padding:2px 8px;text-align:right">{"FREE" if shipping == 0 else f"R {shipping:.2f}"}</td></tr>
    <tr style="font-weight:bold;font-size:14px;border-top:2px solid #ff6b35"><td style="padding:5px 8px">TOTAL</td><td style="padding:5px 8px;text-align:right;color:#ff6b35">R {total:.2f}</td></tr>
  </table>
</div>
<div style="border-top:1px solid #eee;padding-top:8px;font-size:10px;color:#888;text-align:center">
  Thank you for your order! &nbsp;|&nbsp; Poke Bulk SA (Pty) Ltd &nbsp;|&nbsp; Reg. No: 2024/615040/07 &nbsp;|&nbsp; enquiries@pokebulk.co.za
</div>
</body></html>'''
    return html, invoice_num, customer_email


@staff_member_required
def print_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    html, _, _ = _build_invoice_html(order, show_controls=True)
    return HttpResponse(html, content_type='text/html; charset=utf-8')


@staff_member_required
def email_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    html, invoice_num, customer_email = _build_invoice_html(order, show_controls=False)

    if not customer_email:
        messages.error(request, f"Order #{order.id}: customer has no email address on file — nothing sent.")
        return redirect(reverse('admin:orders_order_change', args=[order.id]))

    subject = f'Your PokeBulk SA Invoice — Order #{order.id} ({invoice_num})'
    text_body = strip_tags(html)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        to=[customer_email],
        bcc=['enquiries@pokebulk.co.za'],
    )
    email.attach_alternative(html, 'text/html')

    try:
        email.send(fail_silently=False)
        OrderTracking.objects.create(
            order=order,
            status=order.status,
            note=f'Invoice emailed to {customer_email}.',
            created_by=request.user,
        )
        messages.success(request, f"Invoice for Order #{order.id} emailed to {customer_email}.")
    except Exception as e:
        messages.error(request, f"Failed to email Order #{order.id} invoice: {e}")

    return redirect(reverse('admin:orders_order_change', args=[order.id]))
