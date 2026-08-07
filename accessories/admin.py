from django.contrib import admin
from .models import Accessory


@admin.register(Accessory)
class AccessoryAdmin(admin.ModelAdmin):
    """Michael's full-access management screen -- unrestricted regardless of
    stock/active state (the public API is what enforces "customers only see
    what's in Stock", not this). list_editable on price/stock/is_active
    means the common case (restock, reprice, take something off sale) never
    needs to open the full edit form. The "Add Accessory" button (top right
    of the changelist) IS the easy-add function for anything not pulled in
    by the TCGCSV import -- only name/category/price are required, so a
    one-off item takes seconds to add."""
    list_display = ["sku", "name", "category", "manufacturer", "price", "stock", "in_stock_display", "is_active"]
    list_filter = ["category", "is_active", "manufacturer"]
    search_fields = ["sku", "name", "manufacturer", "description"]
    list_editable = ["price", "stock", "is_active"]
    ordering = ["-created_at"]
    readonly_fields = ["sku", "tcgcsv_product_id", "tcgcsv_category_id", "tcgplayer_url", "source_price_usd", "created_at", "updated_at"]

    fieldsets = [
        ("Accessory Info", {
            "fields": ["name", "category", "manufacturer", "description", "image_url"],
        }),
        ("Pricing & Stock", {
            "fields": ["price", "stock", "is_active"],
        }),
        ("Import Info (read-only)", {
            "fields": ["sku", "tcgcsv_product_id", "tcgcsv_category_id", "tcgplayer_url", "source_price_usd", "created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="In Stock", boolean=True)
    def in_stock_display(self, obj):
        return obj.in_stock
