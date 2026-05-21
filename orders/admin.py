from django.contrib import admin
from django.utils.html import format_html
from .models import Cart, CartItem, Order, OrderItem, OrderTracking


class OrderTrackingInline(admin.TabularInline):
    model = OrderTracking
    extra = 1
    readonly_fields = ['created_at', 'created_by']
    fields = ['status', 'note', 'waybill_number', 'created_by', 'created_at']

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price_at_purchase']

    def subtotal(self, obj):
        return f"R{obj.subtotal:.2f}"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'status_badge', 'total_price',
        'waybill_number', 'delivery_method', 'created_at'
    ]
    list_filter = ['status', 'delivery_method', 'created_at']
    search_fields = ['id', 'user__username', 'user__email', 'waybill_number']
    readonly_fields = ['created_at', 'updated_at', 'user', 'total_price']
    inlines = [OrderItemInline, OrderTrackingInline]

    fieldsets = [
        ('Order', {
            'fields': ['user', 'status', 'total_price', 'stripe_payment_intent', 'created_at', 'updated_at']
        }),
        ('Delivery', {
            'fields': [
                'delivery_method',
                'delivery_address_line1', 'delivery_address_line2',
                'delivery_city', 'delivery_province', 'delivery_postal_code',
            ]
        }),
        ('Courier', {
            'fields': ['courier_name', 'waybill_number', 'courier_tracking_url']
        }),
        ('Notes', {
            'fields': ['customer_note', 'internal_note']
        }),
    ]

    def status_badge(self, obj):
        colors = {
            'pending':   '#888',
            'printed':   '#3B82F6',
            'packed':    '#8B5CF6',
            'booked':    '#F59E0B',
            'ready':     '#10B981',
            'collected': '#059669',
            'invoiced':  '#1D4ED8',
            'cancelled': '#EF4444',
        }
        color = colors.get(obj.status, '#888')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:12px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, OrderTracking) and not instance.pk:
                instance.created_by = request.user
                # Sync waybill back to order if provided
                if instance.waybill_number:
                    instance.order.waybill_number = instance.waybill_number
                    instance.order.save(update_fields=['waybill_number'])
            instance.save()
        formset.save_m2m()


@admin.register(OrderTracking)
class OrderTrackingAdmin(admin.ModelAdmin):
    list_display = ['order', 'status', 'waybill_number', 'created_by', 'created_at']
    list_filter = ['status']
    readonly_fields = ['created_at', 'created_by']


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'total', 'updated_at']
    inlines = [CartItemInline]

