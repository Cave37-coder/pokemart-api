import json
from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.core.exceptions import PermissionDenied
from django.middleware.csrf import get_token
from django.db.models import Q

from products.models import PokemonProduct
from .models import Order, OrderItem, OrderTracking, Cart, CartItem, ManualInvoice, ManualInvoiceItem
from .manual_invoice import build_manual_invoice_html, html_to_pdf
from .manual_invoice_pos import build_pos_html


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
#
# "Add manual invoice" opens a custom POS-style screen (manual_invoice_pos.py)
# instead of the standard Django admin form -- editing an EXISTING invoice
# still uses the normal admin form below, only creation is POS-style.
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
            'fields': ('shipping_cost', 'discount_percent', 'eft_confirmed', 'totals_display')
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
        discount_line = ''
        if obj.discount_percent:
            discount_line = format_html(
                '&nbsp;|&nbsp; Discount ({}%): <strong style="color:#2e7d32">-R {:.2f}</strong> ',
                obj.discount_percent, obj.discount_amount
            )
        return format_html(
            'Subtotal: <strong>R {:.2f}</strong> {}'
            '&nbsp;|&nbsp; Shipping: <strong>R {:.2f}</strong> '
            '&nbsp;|&nbsp; <span style="color:#ff6b35;font-weight:bold">TOTAL: R {:.2f}</span>',
            obj.subtotal, discount_line, obj.shipping_cost or 0, obj.total
        )
    totals_display.short_description = 'Totals (live)'

    def invoice_button(self, obj):
        if not obj.pk:
            return 'Save the invoice first to unlock Print / PDF / Email.'
        print_url = reverse('admin:manual-invoice-print', args=[obj.pk])
        pdf_url = reverse('admin:manual-invoice-pdf', args=[obj.pk])
        email_url = reverse('admin:manual-invoice-email', args=[obj.pk])
        email_confirm_target = obj.customer_email or 'this customer (no email on file)'
        return format_html(
            '''<div style="display:flex;gap:6px;flex-wrap:wrap;white-space:nowrap">
                <a href="{}" target="_blank" style="background:#1a1a24;color:#fff;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;border:1px solid #555;display:inline-block">📄 Print / View</a>
                <a href="{}" target="_blank" style="background:#ff6b35;color:#fff;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;display:inline-block">⬇ PDF</a>
                <a href="{}" onclick="return confirm('Email this invoice to {}? This will send a real email.')" style="background:#2e7d32;color:#fff;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;display:inline-block">✉️ Email</a>
            </div>''',
            print_url, pdf_url, email_url, email_confirm_target
        )
    invoice_button.short_description = 'Invoice'

    # ------------------------------------------------------------------
    # POS screen wiring
    # ------------------------------------------------------------------

    def add_view(self, request, form_url='', extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return redirect(reverse('admin:manual-invoice-pos'))

    def get_urls(self):
        custom = [
            path('<int:pk>/manual-invoice-print/', self.admin_site.admin_view(self.print_invoice_view), name='manual-invoice-print'),
            path('<int:pk>/manual-invoice-pdf/', self.admin_site.admin_view(self.pdf_invoice_view), name='manual-invoice-pdf'),
            path('<int:pk>/manual-invoice-email/', self.admin_site.admin_view(self.email_invoice_view), name='manual-invoice-email'),
            path('pos/', self.admin_site.admin_view(self.pos_view), name='manual-invoice-pos'),
            path('pos/search/', self.admin_site.admin_view(self.pos_search_view), name='manual-invoice-pos-search'),
            path('pos/save/', self.admin_site.admin_view(self.pos_save_view), name='manual-invoice-pos-save'),
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

    def email_invoice_view(self, request, pk):
        invoice = get_object_or_404(ManualInvoice, pk=pk)

        if not invoice.customer_email:
            messages.error(request, f"{invoice.invoice_number}: no customer email on file — nothing sent.")
            return redirect(reverse('admin:orders_manualinvoice_change', args=[invoice.pk]))

        html = build_manual_invoice_html(invoice, show_controls=False)
        subject = f'Your PokeBulk SA Invoice — {invoice.invoice_number}'
        text_body = strip_tags(html)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            to=[invoice.customer_email],
            bcc=['enquiries@pokebulk.co.za'],
        )
        email.attach_alternative(html, 'text/html')

        pdf_bytes = html_to_pdf(html)
        email.attach(f'{invoice.invoice_number}.pdf', pdf_bytes, 'application/pdf')

        try:
            email.send(fail_silently=False)
            messages.success(request, f"{invoice.invoice_number} emailed to {invoice.customer_email}.")
        except Exception as e:
            messages.error(request, f"Failed to email {invoice.invoice_number}: {e}")

        return redirect(reverse('admin:orders_manualinvoice_change', args=[invoice.pk]))

    def pos_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        csrf_token = get_token(request)
        search_url = reverse('admin:manual-invoice-pos-search')
        save_url = reverse('admin:manual-invoice-pos-save')
        cancel_url = reverse('admin:orders_manualinvoice_changelist')
        html = build_pos_html(csrf_token, search_url, save_url, cancel_url)
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    def pos_search_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        term = request.GET.get('term', '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})

        products = PokemonProduct.objects.filter(
            Q(name__icontains=term) | Q(sku__icontains=term) |
            Q(card_set__name__icontains=term) | Q(card_set__code__icontains=term)
        ).select_related('card_set').order_by('-card_set__release_date', 'name')[:30]

        results = [{
            'id': p.id,
            'name': p.name,
            'set_name': p.card_set.name if p.card_set else '',
            'set_code': p.card_set.code if p.card_set else '',
            'card_number': p.card_number or '',
            'variant': p.variant_override or '',
            'price': float(p.price or 0),
        } for p in products]

        return JsonResponse({'results': results})

    def pos_save_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid request body'}, status=400)

        customer_name = (payload.get('customer_name') or '').strip()
        items = payload.get('items') or []

        if not customer_name:
            return JsonResponse({'success': False, 'error': 'Customer name is required.'}, status=400)
        if not items:
            return JsonResponse({'success': False, 'error': 'At least one item is required.'}, status=400)

        try:
            shipping_cost = Decimal(str(payload.get('shipping_cost') or 0))
        except (InvalidOperation, ValueError):
            shipping_cost = Decimal('0')

        try:
            discount_percent = Decimal(str(payload.get('discount_percent') or 0))
            if discount_percent < 0:
                discount_percent = Decimal('0')
            if discount_percent > 100:
                discount_percent = Decimal('100')
        except (InvalidOperation, ValueError):
            discount_percent = Decimal('0')

        invoice = ManualInvoice.objects.create(
            customer_name=customer_name,
            customer_email=(payload.get('customer_email') or '').strip(),
            customer_phone=(payload.get('customer_phone') or '').strip(),
            delivery_note=(payload.get('delivery_note') or '').strip(),
            shipping_cost=shipping_cost,
            discount_percent=discount_percent,
            eft_confirmed=bool(payload.get('eft_confirmed')),
            created_by=request.user,
        )

        for item in items:
            product = None
            product_id = item.get('product_id')
            if product_id:
                product = PokemonProduct.objects.filter(pk=product_id).first()

            try:
                unit_price = Decimal(str(item.get('unit_price'))) if item.get('unit_price') is not None else None
            except (InvalidOperation, ValueError):
                unit_price = None

            try:
                quantity = max(1, int(item.get('quantity') or 1))
            except (ValueError, TypeError):
                quantity = 1

            ManualInvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                description=(item.get('description') or '').strip(),
                set_name=(item.get('set_name') or '').strip(),
                card_number=str(item.get('card_number') or '').strip(),
                variant=(item.get('variant') or '').strip(),
                quantity=quantity,
                unit_price=unit_price,
            )

        return JsonResponse({
            'success': True,
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'redirect_url': reverse('admin:orders_manualinvoice_change', args=[invoice.pk]),
        })
