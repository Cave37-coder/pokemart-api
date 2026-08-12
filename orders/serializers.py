from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, OrderTracking, ManualInvoice
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

    class Meta:
        model = Order
        fields = [
    'id', 'status', 'status_display', 'total_price', 'items',
    'tracking',
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

    class Meta:
        model = Order
        fields = ['status', 'note', 'waybill_number', 'courier_name', 'courier_tracking_url']


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
    is_paid = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'status', 'status_display', 'customer_name', 'customer_email',
            'payment_method', 'payment_method_display', 'eft_confirmed', 'cash_confirmed',
            'stripe_payment_intent', 'is_paid',
            'total_price', 'discount_percent', 'discount_amount', 'shipping_cost',
            'shipping_method', 'delivery_method', 'waybill_number', 'courier_name',
            'courier_tracking_url', 'item_count', 'created_at',
        ]

    def get_customer_name(self, obj):
        full = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full or obj.user.username

    def get_is_paid(self, obj):
        # Same combined logic as OrderAdmin.payment_status_display -- one
        # source of truth duplicated here rather than imported, since
        # admin.py isn't a module DRF serializers should depend on.
        if obj.payment_method == 'payfast':
            return bool(obj.stripe_payment_intent)
        if obj.payment_method == 'eft':
            return obj.eft_confirmed
        if obj.payment_method == 'coc':
            return obj.cash_confirmed
        return False

    def get_item_count(self, obj):
        return sum(i.quantity for i in obj.items.all())


class ManualInvoiceListSerializer(serializers.ModelSerializer):
    """Manual Invoice had zero REST API before this -- it only ever existed
    as Django admin's POS screens (session auth). This is a read-only list
    endpoint purely to feed the new staff dashboard's Manual Invoices tab;
    creating/editing invoices still goes through the existing POS screen
    (linked out to, not rebuilt here) since that flow already works well."""
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = ManualInvoice
        fields = [
            'id', 'invoice_number', 'customer_name', 'customer_email', 'customer_phone',
            'shipping_cost', 'discount_percent', 'discount_amount', 'subtotal', 'total',
            'item_count', 'payment_received', 'payment_method', 'payment_method_display',
            'created_at',
        ]
