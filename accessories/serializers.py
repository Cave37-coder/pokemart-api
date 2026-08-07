from rest_framework import serializers
from .models import Accessory


class AccessorySerializer(serializers.ModelSerializer):
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Accessory
        fields = [
            "id", "sku", "name", "category", "manufacturer", "description",
            "image_url", "price", "stock", "in_stock", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "sku", "created_at", "updated_at"]
