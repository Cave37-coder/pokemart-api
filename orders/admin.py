from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from .models import Order, OrderItem, OrderTracking, Cart, CartItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price_at_purchase']
    can_delete = False


class OrderTrackingInline(admin.TabularInline):
    model = OrderTracking
    extra = 0
    readonly_fields = ['status', 'note', 'waybill_number', 'created_by', 'created_at']
    can_delete = False
    ordering = ['created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'payment_method', 'payment_confirmed', 'eft_confirmed', 'total_price', 'shipping_method', 'waybill_number', 'created_at', 'print_button']
    list_filter = ['status', 'payment_method', 'payment_confirmed', 'eft_confirmed', 'delivery_method']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'waybill_number']
    readonly_fields = ['created_at', 'updated_at', 'print_button', 'customer_info', 'shipping_display', 'invoice_total_display']
    ordering = ['-created_at']
    inlines = [OrderItemInline, OrderTrackingInline]

    fieldsets = (
        ('Order Info', {
            'fields': (
                ('user', 'customer_info'),
                'status',
                'payment_confirmed',
                'payment_confirmed_method',
                ('total_price', 'shipping_display', 'invoice_total_display'),
                'created_at', 'updated_at', 'print_button',
            )
        }),
        ('Payment', {
            'fields': ('payment_method', 'eft_confirmed', 'stripe_payment_intent')
        }),
        ('Shipping', {
            'fields': ('delivery_method', 'shipping_method', 'shipping_cost')
        }),
        ('Delivery Address', {
            'fields': ('delivery_address_line1', 'delivery_address_line2', 'delivery_city', 'delivery_province', 'delivery_postal_code')
        }),
        ('Pudo', {
            'fields': ('pudo_locker_name', 'pudo_locker_address')
        }),
        ('Courier', {
            'fields': ('waybill_number', 'courier_name', 'courier_tracking_url')
        }),
        ('Notes', {
            'fields': ('customer_note', 'internal_note')
        }),
    )

    def customer_info(self, obj):
        if not obj.pk or not obj.user:
            return '-'
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip() or '—'
        phone = getattr(obj.user, 'phone_number', '') or '—'
        return format_html(
            '<strong>{}</strong> &nbsp;|&nbsp; 📞 {}',
            full_name, phone
        )
    customer_info.short_description = 'Name / Contact No'

    def shipping_display(self, obj):
        if not obj.pk:
            return '-'
        return f"R {float(obj.shipping_cost or 0):.2f}"
    shipping_display.short_description = 'Shipping'

    def invoice_total_display(self, obj):
        """Live total = subtotal of current line items + shipping_cost, calculated
        the same way the printed invoice does. Compare against the stored
        'Total price' field above — if they don't match, total_price is stale
        (e.g. an order placed before the shipping-fee checkout fix) and should
        be corrected manually."""
        if not obj.pk:
            return '-'
        subtotal = sum(float(i.price_at_purchase) * i.quantity for i in obj.items.all())
        total = subtotal + float(obj.shipping_cost or 0)
        stored = float(obj.total_price or 0)
        mismatch = abs(total - stored) > 0.01
        color = '#ff4444' if mismatch else '#2e7d32'
        note = ' ⚠ differs from Total price' if mismatch else ''
        return format_html('<strong style="color:{}">R {:.2f}</strong>{}', color, total, note)
    invoice_total_display.short_description = 'Total (live)'

    def print_button(self, obj):
        if obj.pk:
            pull_url = reverse('print-order', args=[obj.pk])
            inv_url = reverse('print-invoice', args=[obj.pk])
            email_url = reverse('email-order-invoice', args=[obj.pk])
            return format_html(
                '''<a href="{}" target="_blank" style="background:#ff6b35;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;margin-right:6px">🖨 Pull Sheet</a>
                <a href="{}" target="_blank" style="background:#1a1a24;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;border:1px solid #555;margin-right:6px">📄 Invoice</a>
                <a href="{}" onclick="return confirm('Email the invoice to {}? This will send a real email.')" style="background:#2e7d32;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px">✉️ Email Order</a>''',
                pull_url, inv_url, email_url, obj.user.email or 'this customer'
            )
        return '-'
    print_button.short_description = 'Print'

    def get_urls(self):
        urls = super().get_urls()
        return urls


@admin.register(OrderTracking)
class OrderTrackingAdmin(admin.ModelAdmin):
    list_display = ['order', 'status', 'note', 'created_at']
    list_filter = ['status']
    readonly_fields = ['created_at']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
