from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Order, OrderItem, OrderTracking, Cart, CartItem, ManualInvoice, ManualInvoiceItem
from .manual_invoice import build_manual_invoice_html, html_to_pdf


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


# =============================================================================
# MANUAL INVOICE — standalone admin-only invoicing tool. Search the real
# catalog for pricing, or type in off-site stock by hand. EFT-only. Never
# touches PokemonProduct.stock, Cart, or Order in any way.
# =============================================================================

class ManualInvoiceItemInline(admin.TabularInline):
    model = ManualInvoiceItem
    extra = 3
    autocomplete_fields = ['product']
    fields = ['product', 'description', 'set_name', 'card_number', 'variant', 'quantity', 'unit_price', 'line_total_display']
    readonly_fields = ['line_total_display']

    def line_total_display(self, obj):
        if obj and obj.pk:
            return f"R {obj.line_total:.2f}"
        return "-"
    line_total_display.short_description = 'Line Total'


@admin.register(ManualInvoice)
class ManualInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer_name', 'item_count_display', 'total_display', 'eft_confirmed', 'created_at', 'invoice_button']
    list_filter = ['eft_confirmed', 'created_at']
    search_fields = ['invoice_number', 'customer_name', 'customer_email']
    readonly_fields = ['invoice_number', 'created_at', 'updated_at', 'totals_display', 'invoice_button']
    ordering = ['-created_at']
    inlines = [ManualInvoiceItemInline]

    fieldsets = (
        ('Invoice', {
            'fields': ('invoice_number', 'created_at', 'updated_at', 'invoice_button')
        }),
        ('Customer', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('Delivery', {
            'fields': ('delivery_note',)
        }),
        ('Payment (EFT only)', {
            'fields': ('shipping_cost', 'eft_confirmed', 'totals_display')
        }),
        ('Notes', {
            'fields': ('internal_note',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def item_count_display(self, obj):
        return obj.item_count if obj.pk else 0
    item_count_display.short_description = 'Items'

    def total_display(self, obj):
        return f"R {obj.total:.2f}" if obj.pk else '-'
    total_display.short_description = 'Total'

    def totals_display(self, obj):
        if not obj.pk:
            return 'Save the invoice first, then add line items below.'
        return format_html(
            'Subtotal: <strong>R {:.2f}</strong> &nbsp;|&nbsp; Shipping: <strong>R {:.2f}</strong> '
            '&nbsp;|&nbsp; <span style="color:#ff6b35;font-weight:bold">TOTAL: R {:.2f}</span>',
            obj.subtotal, obj.shipping_cost or 0, obj.total
        )
    totals_display.short_description = 'Totals (live)'

    def invoice_button(self, obj):
        if not obj.pk:
            return 'Save the invoice first to unlock Print / PDF.'
        print_url = reverse('admin:manual-invoice-print', args=[obj.pk])
        pdf_url = reverse('admin:manual-invoice-pdf', args=[obj.pk])
        return format_html(
            '''<a href="{}" target="_blank" style="background:#1a1a24;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;border:1px solid #555;margin-right:6px">📄 Print / View Invoice</a>
            <a href="{}" target="_blank" style="background:#ff6b35;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px">⬇ Download PDF</a>''',
            print_url, pdf_url
        )
    invoice_button.short_description = 'Invoice'

    def get_urls(self):
        custom = [
            path('<int:pk>/manual-invoice-print/', self.admin_site.admin_view(self.print_invoice_view), name='manual-invoice-print'),
            path('<int:pk>/manual-invoice-pdf/', self.admin_site.admin_view(self.pdf_invoice_view), name='manual-invoice-pdf'),
        ]
        return custom + super().get_urls()

    def print_invoice_view(self, request, pk):
        invoice = get_object_or_404(ManualInvoice, pk=pk)
        html = build_manual_invoice_html(invoice, show_controls=True)
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    def pdf_invoice_view(self, request, pk):
        invoice = get_object_or_404(ManualInvoice, pk=pk)
        html = build_manual_invoice_html(invoice, show_controls=False)
        pdf_bytes = html_to_pdf(html)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}.pdf"'
        return response
