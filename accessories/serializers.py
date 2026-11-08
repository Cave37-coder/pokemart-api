from rest_framework import serializers
from .models import Accessory


class AccessorySerializer(serializers.ModelSerializer):
    in_stock = serializers.BooleanField(read_only=True)
    # The product id My Pile takes (POST /api/cart/add/ product_id=...).
    cart_product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Accessory
        fields = [
            "id", "sku", "name", "category", "manufacturer", "description",
            "image_url", "price", "stock", "in_stock", "is_active", "cart_product_id",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "sku", "created_at", "updated_at"]
