from django.contrib import admin
from django.utils.html import format_html
from .models import Cart, CartItem, Order, OrderItem, OrderTracking

class OrderTrackingInline(admin.TabularInline):
    model = OrderTracking
    extra = 1
    readonly_fields = ["created_at", "created_by"]
    fields = ["status", "note", "waybill_number", "created_by", "created_at"]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "quantity", "price_at_purchase"]

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "status_badge", "payment_badge", "eft_confirmed", "total_price", "shipping_method", "waybill_number", "created_at", "print_slip"]
    list_filter = ["status", "payment_method", "eft_confirmed", "delivery_method", "created_at"]
    search_fields = ["id", "user__username", "user__email", "waybill_number"]
    readonly_fields = ["created_at", "updated_at", "user", "total_price"]
    list_editable = ["eft_confirmed"]
    inlines = [OrderItemInline, OrderTrackingInline]
    fieldsets = [
        ("Order", {"fields": ["user", "status", "total_price", "created_at", "updated_at"]}),
        ("Payment", {"fields": ["payment_method", "eft_confirmed", "stripe_payment_intent"]}),
        ("Shipping", {"fields": ["shipping_method", "shipping_cost", "delivery_method"]}),
        ("Delivery Address", {"fields": ["delivery_address_line1", "delivery_address_line2", "delivery_city", "delivery_province", "delivery_postal_code", "pudo_locker_name", "pudo_locker_address"]}),
        ("Courier", {"fields": ["courier_name", "waybill_number", "courier_tracking_url"]}),
        ("Notes", {"fields": ["customer_note", "internal_note"]}),
    ]

    def status_badge(self, obj):
        colors = {
            "pending": "#888", "pending_eft": "#F59E0B", "printed": "#3B82F6",
            "packed": "#8B5CF6", "booked": "#F59E0B", "ready": "#10B981",
            "collected": "#059669", "invoiced": "#1D4ED8", "cancelled": "#EF4444",
        }
        color = colors.get(obj.status, "#888")
        return format_html('<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:12px">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def payment_badge(self, obj):
        colors = {"payfast": "#1D4ED8", "eft": "#F59E0B", "coc": "#10B981"}
        labels = {"payfast": "PayFast", "eft": "EFT", "coc": "COC"}
        color = colors.get(obj.payment_method, "#888")
        label = labels.get(obj.payment_method, obj.payment_method)
        return format_html('<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:12px">{}</span>', color, label)
    payment_badge.short_description = "Payment"

    def print_slip(self, obj):
        return format_html('<a href="/api/print/order/{}/" target="_blank" style="background:#ff6b35;color:#fff;padding:4px 12px;border-radius:6px;text-decoration:none;font-size:12px">Print</a>', obj.id)
    print_slip.short_description = "Print"

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, OrderTracking) and not instance.pk:
                instance.created_by = request.user
                if instance.waybill_number:
                    instance.order.waybill_number = instance.waybill_number
                    instance.order.save(update_fields=["waybill_number"])
            instance.save()
        formset.save_m2m()

@admin.register(OrderTracking)
class OrderTrackingAdmin(admin.ModelAdmin):
    list_display = ["order", "status", "waybill_number", "created_by", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at", "created_by"]

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["user", "total", "updated_at"]
    inlines = [CartItemInline]
