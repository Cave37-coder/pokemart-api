from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, OrderTracking
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
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total', 'updated_at']


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
    'delivery_method', 'delivery_address_line1', 'delivery_address_line2',
    'delivery_city', 'delivery_province', 'delivery_postal_code',
    'waybill_number', 'courier_name', 'courier_tracking_url',
    'customer_note', 'created_at',
     ]
        read_only_fields = ['id', 'status', 'total_price', 'created_at']


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    note = serializers.CharField(required=False, allow_blank=True)
    waybill_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = ['status', 'note', 'waybill_number', 'courier_name', 'courier_tracking_url']
