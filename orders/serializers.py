from decimal import Decimal
from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, OrderTracking, ManualInvoice, BuyOrder, BuyOrderItem
from products.serializers import PokemonProductSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = PokemonProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('products').models.PokemonProduct.objects.all(),
        source='product', write_only=True
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'subtotal']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    # Post-discount total -- unchanged field name so every existing caller
    # (pile/checkout pages) keeps working, it now just already has the
    # community discount baked in. subtotal/discount_percent/discount_amount
    # above are the new fields the frontend uses to show the breakdown.
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'items', 'subtotal', 'discount_percent', 'discount_amount', 'total', 'updated_at']


class OrderTrackingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OrderTracking
        fields = ['id', 'status', 'status_display', 'note', 'waybill_number', 'created_at']


class OrderItemSerializer(serializers.ModelSerializer):
    product = PokemonProductSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_sku', 'quantity', 'price_at_purchase', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    tracking = OrderTrackingSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    # 2026-10-23: read-only, so the status page can show banking details on EFT /
    # Cash-on-Collection orders.
    payment_method = serializers.CharField(read_only=True)
    # Store credit (2026-10-27): credit used + what is still to pay.
    store_credit_applied = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = [
    'id', 'status', 'status_display', 'total_price', 'items',
    'tracking', 'payment_method', 'store_credit_applied', 'amount_due',
    'shipping_cost', 'discount_percent', 'discount_amount',
    'delivery_method', 'delivery_address_line1', 'delivery_address_line2',
    'delivery_city', 'delivery_province', 'delivery_postal_code',
    'waybill_number', 'courier_name', 'courier_tracking_url',
    'customer_note', 'created_at',
     ]
        read_only_fields = ['id', 'status', 'total_price', 'created_at', 'shipping_cost', 'discount_percent', 'discount_amount']


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    note = serializers.CharField(required=False, allow_blank=True)
    waybill_number = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES, required=False)
    # Payment confirmation (2026-08-12) -- documents the same fields
    # OrderStatusUpdateView actually reads off request.data. All optional:
    # a request can update just status, just payment confirmation, or both
    # in one PATCH.
    eft_confirmed = serializers.BooleanField(required=False)
    cash_confirmed = serializers.BooleanField(required=False)
    stripe_payment_intent = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = [
            'status', 'note', 'waybill_number', 'courier_name', 'courier_tracking_url',
            'eft_confirmed', 'cash_confirmed', 'stripe_payment_intent',
        ]


# =============================================================================
# STAFF ORDERS DASHBOARD (2026-08-12) — Michael: "build an admin app...
# basically a full Orders app" so status updates / Pull Sheet / Invoice
# printing can happen without going through Django admin's own templates.
# Deliberately a LEAN list serializer (no nested items/product data) since
# this backs a changelist-style table, not an order detail view — matches
# exactly the columns OrderAdmin's own changelist already shows (customer,
# status, paid, price, discount, shipping, total). Full item detail is
# still available via the existing OrderDetailView if ever needed.
# =============================================================================

class AdminOrderListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.CharField(source='user.email', read_only=True)
    customer_phone = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()
    paid_via = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'status', 'status_display', 'customer_name', 'customer_email', 'customer_phone',
            'payment_method', 'payment_method_display', 'eft_confirmed', 'cash_confirmed',
            'stripe_payment_intent', 'is_paid', 'paid_via',
            'total_price', 'discount_percent', 'discount_amount', 'shipping_cost',
            'store_credit_applied', 'amount_due',
            'shipping_method', 'delivery_method', 'waybill_number', 'courier_name',
            'courier_tracking_url', 'item_count', 'created_at',
            # delivery details -- prefill the staff "Change delivery" form
            'pudo_locker_name', 'pudo_locker_address',
            'delivery_address_line1', 'delivery_address_line2',
            'delivery_city', 'delivery_province', 'delivery_postal_code',
        ]

    def get_customer_name(self, obj):
        full = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full or obj.user.username

    def get_customer_phone(self, obj):
        return getattr(obj.user, 'phone_number', '') or ''

    def get_is_paid(self, obj):
        # Decoupled from payment_method (2026-08-14) -- Michael: "customer
        # selects 'Cash on Collection', payments have been made by EFT or
        # Payfast on collection... need to show customers option selected
        # and then actual payment method used". A customer's checkout
        # choice no longer gates which confirmation flag counts -- any of
        # the three actually being confirmed marks the order paid,
        # regardless of what was originally selected. PayFast stays the
        # only fully automatic one (driven purely by stripe_payment_intent
        # from the webhook); EFT/Cash are staff-ticked. Same logic
        # duplicated in OrderAdmin.payment_status_display/PaidFilter --
        # not imported since admin.py shouldn't be a DRF serializer dependency.
        return bool(obj.stripe_payment_intent) or obj.eft_confirmed or obj.cash_confirmed or obj.paid_by_credit

    def get_paid_via(self, obj):
        """Which method actually got confirmed, which may differ from the
        customer's payment_method selection at checkout. None if unpaid."""
        if obj.stripe_payment_intent:
            return 'PayFast'
        if obj.eft_confirmed:
            return 'EFT'
        if obj.cash_confirmed:
            return 'Cash'
        if obj.paid_by_credit:
            return 'Store Credit'
        return None

    def get_item_count(self, obj):
        return sum(i.quantity for i in obj.items.all())


# =============================================================================
# BUYING INVOICES (2026-10-13) -- staff dashboard view of BuyOrder. Draft ->
# Paid -> Complete; completing adds catalogue lines to live website stock.
# =============================================================================

class BuyInvoiceItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    product_id = serializers.IntegerField(read_only=True)
    accessory_id = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()
    live_stock = serializers.SerializerMethodField()
    tcg_price = serializers.SerializerMethodField()
    effective_unit_cost = serializers.SerializerMethodField()
    effective_rate = serializers.SerializerMethodField()
    live_price = serializers.SerializerMethodField()
    sorted_qty = serializers.IntegerField(read_only=True)
    remaining_qty = serializers.IntegerField(read_only=True)
    sorts = serializers.SerializerMethodField()

    class Meta:
        model = BuyOrderItem
        fields = ['id', 'product_id', 'accessory_id', 'image_url', 'description', 'set_name', 'card_number', 'variant',
                  'quantity', 'unit_price', 'line_total', 'live_stock', 'tcg_price',
                  'condition', 'sell_price', 'sell_pct', 'live_price', 'effective_unit_cost', 'effective_rate',
                  'bundle_type', 'sorted_qty', 'remaining_qty', 'sorts']

    def get_sorts(self, obj):
        # Bulk buy-in: cards already sorted out of this bundle into stock (newest first).
        return [{
            'id': s.id, 'name': s.product.name if s.product else '(deleted card)',
            'set_name': s.product.card_set.name if s.product and s.product.card_set else '',
            'card_number': (s.product.card_number if s.product else '') or '',
            'variant': (s.product.variant_override if s.product else '') or 'N',
            'quantity': s.quantity, 'condition': s.condition,
            'unit_cost': str(s.unit_cost.quantize(Decimal('0.01'))), 'created_at': s.created_at.isoformat(),
        } for s in obj.sorts.all()]

    def get_live_stock(self, obj):
        if obj.product:
            return obj.product.stock
        return obj.accessory.stock if obj.accessory_id and obj.accessory else None

    def get_image_url(self, obj):
        if obj.accessory_id and obj.accessory:
            return obj.accessory.image_url or None
        return None

    def get_tcg_price(self, obj):
        # Snapshot taken when the line was saved (condition-adjusted), so the
        # price lock / later syncs don't change what an old invoice shows.
        if obj.tcg_price is not None:
            return str(obj.tcg_price)
        return str(obj.product.price) if obj.product else None

    def get_live_price(self, obj):
        # What the card is listed at on the site right now (moves with the
        # nightly sync when a sell % is set) -- the 'selling value' for margin.
        target = obj.stock_product or obj.product
        if target is None and obj.accessory_id and obj.accessory:
            target = obj.accessory
        return str(target.price) if target is not None else None

    def get_effective_unit_cost(self, obj):
        # Real cost per unit: line price scaled to what was actually paid.
        return str(obj.buy_order.effective_unit_cost(obj).quantize(Decimal('0.01')))

    def get_effective_rate(self, obj):
        # Effective cost as % of the TCG price snapshot (None if no TCG price).
        if not obj.tcg_price:
            return None
        return str((obj.buy_order.effective_unit_cost(obj) / obj.tcg_price * 100).quantize(Decimal('0.1')))


class BuyInvoiceSerializer(serializers.ModelSerializer):
    """List + detail. `items` is included (invoices are small); the list view
    prefetches them so this stays a handful of queries."""
    items = BuyInvoiceItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    off_catalogue_units = serializers.SerializerMethodField()
    bundle_units = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, default=None)
    analysis = serializers.SerializerMethodField()
    # Store credit (2026-10-27)
    amount_owed = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    cash_portion = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    user_credit_balance = serializers.SerializerMethodField()

    class Meta:
        model = BuyOrder
        fields = [
            'id', 'buy_number', 'kind', 'box_number', 'status', 'status_display', 'stock_mode', 'stock_applied',
            'seller_name', 'seller_email', 'seller_phone', 'user_id', 'user_username',
            'seller_note', 'internal_note',
            'payment_made', 'payment_method', 'payment_method_display',
            'total', 'amount_paid', 'cost_applied', 'premium_accepted', 'analysis', 'item_count', 'off_catalogue_units', 'bundle_units',
            'store_credit_amount', 'amount_owed', 'cash_portion', 'user_credit_balance',
            'created_at', 'completed_at', 'items',
        ]

    def get_off_catalogue_units(self, obj):
        # Bulk bundles are counted separately (bundle_units), not as off-catalogue.
        return sum(i.quantity for i in obj.items.all() if not i.product_id and not i.accessory_id and not i.bundle_type)

    def get_bundle_units(self, obj):
        return sum(i.quantity for i in obj.items.all() if i.bundle_type)

    def get_user_credit_balance(self, obj):
        if not obj.user_id:
            return None
        from store_credit.services import balance
        return str(balance(obj.user_id))

    def get_analysis(self, obj):
        """Rates + profit view: what the line prices said we'd pay, what we
        really paid, and what the sell prices should return."""
        items = list(obj.items.all())
        total = obj.total
        actual = obj.amount_paid if obj.amount_paid is not None else total
        factor = obj.allocation_factor
        tcg_total = sum(((i.tcg_price or Decimal('0')) * i.quantity for i in items), Decimal('0'))
        def selling(i):
            # Completed invoices: the live site price (fluid); otherwise the planned sell price.
            tgt = (i.stock_product or i.product) if obj.status == 'complete' else None
            return tgt.price if (tgt is not None and i.sell_price) else i.sell_price
        sell_total = sum(((selling(i) or Decimal('0')) * i.quantity for i in items if i.sell_price), Decimal('0'))
        cost_sell_lines = sum((obj.effective_unit_cost(i) * i.quantity for i in items if i.sell_price), Decimal('0'))
        def pct(a, b):
            return str((a / b * 100).quantize(Decimal('0.1'))) if b else None
        return {
            'invoice_total': str(total),
            'actual_paid': str(actual),
            'difference': str((total - actual).quantize(Decimal('0.01'))),  # + = paid less than the invoice said
            'allocation_factor': str(factor.quantize(Decimal('0.0001'))),
            'tcg_total': str(tcg_total.quantize(Decimal('0.01'))),
            'nominal_rate': pct(total, tcg_total),
            'effective_rate': pct(actual, tcg_total),
            'expected_sell_total': str(sell_total.quantize(Decimal('0.01'))),
            'expected_profit': str((sell_total - cost_sell_lines).quantize(Decimal('0.01'))) if sell_total else None,
            'expected_margin': pct(sell_total - cost_sell_lines, sell_total) if sell_total else None,
        }


class ManualInvoiceListSerializer(serializers.ModelSerializer):
    """Manual Invoice had zero REST API before this -- it only ever existed
    as Django admin's POS screens (session auth). This is a read-only list
    endpoint purely to feed the new staff dashboard's Manual Invoices tab;
    creating/editing invoices still goes through the existing POS screen
    (linked out to, not rebuilt here) since that flow already works well."""
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    # Linked site account (2026-08-12), if one was picked on the POS screen
    # -- read-only here, null when this is a plain walk-in with no account.
    user_id = serializers.IntegerField(source='user.id', read_only=True, default=None)
    user_username = serializers.CharField(source='user.username', read_only=True, default=None)

    class Meta:
        model = ManualInvoice
        fields = [
            'id', 'invoice_number', 'status', 'status_display', 'customer_name', 'customer_email', 'customer_phone',
            'user_id', 'user_username',
            'shipping_cost', 'discount_percent', 'discount_amount', 'subtotal', 'total',
            'store_credit_applied', 'amount_due',
            'item_count', 'payment_received', 'payment_method', 'payment_method_display',
            'created_at',
        ]
