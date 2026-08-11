import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.core.exceptions import PermissionDenied, ValidationError
from django.middleware.csrf import get_token
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

from products.models import PokemonProduct

# Variant codes staff can assign to a card (matches variant_override values
# used across the catalog). Defined here rather than imported from a
# products-app module, since no such module exists in the live project --
# products/urls.py wires its own "manage/" screen straight to a function
# inside products/views.py, not a separate manage_set_view.py file.
VARIANT_CHOICES = [
    ('N', 'Normal'),
    ('H', 'Holo'),
    ('RH', 'Reverse Holo'),
    ('FE', '1st Edition'),
    ('PB', 'Poke Ball'),
    ('MB', 'Master Ball'),
    ('FB', 'Friend Ball'),
    ('LB', 'Love Ball'),
    ('QB', 'Quick Ball'),
    ('DB', 'Dusk Ball'),
]
from .models import Order, OrderItem, OrderTracking, Cart, CartItem, ManualInvoice, ManualInvoiceItem, BuyOrder, BuyOrderItem
from .manual_invoice import build_manual_invoice_html, build_manual_invoice_pull_sheet_html, html_to_pdf
from .manual_invoice_pos import build_pos_html
from .buy_order_document import build_buy_order_html, html_to_pdf as buy_order_html_to_pdf
from .widgets import StatusStepperWidget


class PaidFilter(admin.SimpleListFilter):
    """Filters on the same combined logic as OrderAdmin.payment_status_display:
    PayFast counts as paid once the webhook has written a PF Payment ID into
    stripe_payment_intent; EFT/Cash count as paid via their own manual-tick
    booleans. (Status is NOT part of this — confirmed via Order #117's real
    tracking log that status stays 'Order Received' whether or not PayFast
    has actually confirmed the payment.)"""
    title = 'Paid'
    parameter_name = 'paid'

    def lookups(self, request, model_admin):
        return (('yes', 'Paid'), ('no', 'Unpaid'))

    def _paid_q(self):
        return (
            (Q(payment_method='payfast') & ~Q(stripe_payment_intent=''))
            | Q(payment_method='eft', eft_confirmed=True)
            | Q(payment_method='coc', cash_confirmed=True)
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(self._paid_q())
        if self.value() == 'no':
            return queryset.exclude(self._paid_q())
        return queryset


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price_at_purchase']
    can_delete = False

    def get_queryset(self, request):
        # product is rendered as a readonly field for every row -- without
        # this, each row is its own extra remote query against Railway.
        # An order with N items paid N extra round trips just for this inline.
        return super().get_queryset(request).select_related('product')


class OrderTrackingInline(admin.TabularInline):
    model = OrderTracking
    extra = 0
    readonly_fields = ['status', 'note', 'waybill_number', 'created_by', 'created_at']
    can_delete = False
    ordering = ['created_at']

    def get_queryset(self, request):
        # Same issue as OrderItemInline above, for created_by.
        return super().get_queryset(request).select_related('created_by')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    save_on_top = True
    # Django's built-in "show counts" sidebar feature (the _facets=True
    # toggle) counts each status choice using get_queryset() as its base --
    # but our get_queryset() below already excludes Cancelled/Complete by
    # default, so those two counts always show (0) even when real orders
    # exist in that status. The underlying filter still works correctly
    # (clicking Cancelled/Complete shows the real orders) -- only the
    # number next to them was wrong. Disabling facets here since a
    # permanently-lying count is worse than no count.
    show_facets = admin.ShowFacets.NEVER

    class Media:
        # Tightens changelist row height + form-row padding. See
        # orders/static/orders/order_admin_compact.css — standard per-app
        # static folder, picked up automatically by Django's default
        # AppDirectoriesFinder. Run collectstatic if it's not showing up.
        css = {'all': ('orders/order_admin_compact.css',)}

    list_display = ['id', 'customer_name_display', 'status_badge', 'payment_status_display', 'subtotal_display', 'discount_col', 'shipping_col', 'total_price', 'shipping_method', 'waybill_number', 'created_at', 'print_button']
    list_filter = ['status', PaidFilter, 'payment_method', 'delivery_method']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'waybill_number']
    readonly_fields = ['created_at', 'updated_at', 'print_button', 'customer_info', 'shipping_display', 'invoice_total_display', 'payment_status_display']
    ordering = ['-created_at']
    inlines = [OrderItemInline, OrderTrackingInline]

    fieldsets = (
        ('Order Summary', {
            'fields': (
                ('user', 'customer_info'),
                'status',
                ('payment_method', 'eft_confirmed', 'cash_confirmed', 'payment_status_display'),
                ('discount_percent', 'discount_amount'),
                ('total_price', 'shipping_display', 'invoice_total_display'),
                'print_button',
                ('created_at', 'updated_at'),
            )
        }),
        ('Technical', {
            'fields': ('stripe_payment_intent',),
            'classes': ('collapse',),
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
            'fields': ('customer_note', 'invoice_note', 'internal_note')
        }),
    )

    def has_add_permission(self, request):
        # Real orders only ever come through checkout. Anything created by
        # hand goes through Manual Invoice's POS screen instead — this
        # button was dead weight on the changelist.
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'status':
            kwargs['widget'] = StatusStepperWidget(choices=Order.STATUS_CHOICES)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('user')
        # Default view = open orders only. Explicitly filtering the Status
        # sidebar to Cancelled or Complete still works normally — this only
        # applies when no status filter is set at all.
        if 'status__exact' not in request.GET and 'status__in' not in request.GET:
            qs = qs.exclude(status__in=['cancelled', 'invoiced'])
        return qs

    def get_object(self, request, object_id, from_field=None):
        # Django reuses get_queryset() above for single-object lookups too
        # (this is what powers the change/detail page) -- so clicking into
        # any Complete or Cancelled order, from a filtered list, Recent
        # Actions, or a bookmarked link, hit the same status exclusion and
        # 404'd with "Order with ID '115' doesn't exist. Perhaps it was
        # deleted?" even though it's still very much in the DB. The
        # exclusion should only ever apply to the changelist's default view,
        # never to opening a specific order directly. Mirrors Django's own
        # ModelAdmin.get_object() but against the real, unfiltered queryset.
        queryset = admin.ModelAdmin.get_queryset(self, request).select_related('user')
        model = queryset.model
        field = model._meta.pk if from_field is None else model._meta.get_field(from_field)
        try:
            object_id = field.to_python(object_id)
            return queryset.get(**{field.name: object_id})
        except (model.DoesNotExist, ValidationError, ValueError):
            return None

    def customer_name_display(self, obj):
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full_name or obj.user.username
    customer_name_display.short_description = 'Customer'
    customer_name_display.admin_order_field = 'user__first_name'

    def status_badge(self, obj):
        color_map = {
            'awaiting_payment': '#c62828',  # red — blocked, needs payment
            'pending_eft':      '#e65100',  # deep orange — blocked, needs EFT
            'pending':          '#f9a825',  # amber — just received
            'printed':          '#1565c0',  # blue — processing
            'packed':           '#6a1b9a',  # purple — processing
            'booked':           '#00838f',  # teal — processing
            'ready':            '#00acc1',  # cyan — near done
            'collected':        '#43a047',  # green — collected
            'invoiced':         '#1b5e20',  # dark green — complete
            'cancelled':        '#757575',  # grey — closed
        }
        color = color_map.get(obj.status, '#333')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold;white-space:nowrap">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def payment_status_display(self, obj):
        """Single 'Paid' indicator combining all three payment_method paths.
        PayFast confirmed via a webhook writing the PF Payment ID into
        stripe_payment_intent (confirmed against Order #117's real tracking
        log — status stays 'Order Received' throughout, it does NOT change
        on payment, so status can't be used as the signal). eft_confirmed
        covers EFT; cash_confirmed covers Cash on Collection."""
        if not obj.pk:
            return '-'
        method = obj.payment_method
        if method == 'payfast':
            confirmed = bool(obj.stripe_payment_intent)
            label = 'PayFast'
        elif method == 'eft':
            confirmed = obj.eft_confirmed
            label = 'EFT'
        elif method == 'coc':
            confirmed = obj.cash_confirmed
            label = 'Cash on Collection'
        else:
            confirmed = False
            label = obj.get_payment_method_display() or 'Unknown'
        color = '#2e7d32' if confirmed else '#c62828'
        icon = '✅' if confirmed else '❌'
        return format_html('<strong style="color:{}">{} {} — {}</strong>', color, icon, label, 'Paid' if confirmed else 'Unpaid')
    payment_status_display.short_description = 'Paid'

    def subtotal_display(self, obj):
        # total_price already has the discount subtracted (see CheckoutView),
        # so the raw item subtotal is total_price - shipping + discount.
        return f"{float(obj.total_price or 0) - float(obj.shipping_cost or 0) + float(obj.discount_amount or 0):.2f}"
    subtotal_display.short_description = 'Price'

    def discount_col(self, obj):
        if not obj.discount_amount:
            return '-'
        return format_html('<span style="color:#2e7d32">-R {:.2f} ({:.0f}%)</span>', obj.discount_amount, obj.discount_percent)
    discount_col.short_description = 'Discount'

    def shipping_col(self, obj):
        return f"{float(obj.shipping_cost or 0):.2f}"
    shipping_col.short_description = 'Shipping'

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
        total = subtotal - float(obj.discount_amount or 0) + float(obj.shipping_cost or 0)
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

def _send_manual_invoice_email(invoice):
    """
    Shared by both the manual "Email" button (email_invoice_view) and the
    automatic send that now fires once, right when a new invoice is created
    in pos_save_view. Same content either way -- one source of truth.

    Michael, 2026-08-02: kept as a plain function returning (ok, detail)
    instead of raising, since the automatic call site has no request/response
    to hang a Django admin message off of. Callers decide what to do with
    the result -- email_invoice_view still shows messages.success/error,
    pos_save_view just logs and reports it back in the JSON response.

    "bcc must still happen, without customer email address" (Michael,
    2026-08-02): enquiries@ gets a copy of every invoice regardless of
    whether the customer has an email on file -- walk-in/cash customers
    included. When there's no customer_email there's nothing to put in
    "to" (and some providers, MailerSend included, don't reliably deliver
    a message with an empty "to" and only a bcc), so in that case
    enquiries@ becomes the direct "to" recipient instead of a bcc -- same
    inbox ends up with the copy either way, just not silently blind-copied
    when it's the only recipient.
    """
    # Michael, 2026-08-02: the whole body used to only wrap email.send() in
    # try/except -- building the HTML, generating the PDF (xhtml2pdf), and
    # constructing the EmailMultiAlternatives were all outside it. If any of
    # those steps ever threw, the exception escaped this function entirely.
    # For the automatic send that's especially bad: it runs inside
    # transaction.on_commit in pos_save_view, AFTER the invoice was already
    # saved to the DB -- an uncaught exception there crashes the save
    # request with a 500 *after* the data is already committed, so you'd
    # see "network error saving invoice" even though the invoice actually
    # saved, and no email would ever be attempted, with nothing telling you
    # why. Wrapping the entire thing means every failure mode reports back
    # as (False, detail) instead of silently blowing up the caller.
    try:
        html = build_manual_invoice_html(invoice, show_controls=False)
        subject = f'Your PokeBulk SA Invoice — {invoice.invoice_number}'
        text_body = strip_tags(html)

        if invoice.customer_email:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                to=[invoice.customer_email],
                bcc=['enquiries@pokebulk.co.za'],
            )
        else:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                to=['enquiries@pokebulk.co.za'],
            )
        email.attach_alternative(html, 'text/html')

        pdf_bytes = html_to_pdf(html)
        email.attach(f'{invoice.invoice_number}.pdf', pdf_bytes, 'application/pdf')

        email.send(fail_silently=False)
        if invoice.customer_email:
            return True, f"emailed to {invoice.customer_email}."
        return True, "no customer email on file — copy sent to enquiries@ only."
    except Exception as e:
        logger.exception("Failed to email manual invoice %s", invoice.invoice_number)
        return False, f"failed to send: {e}"


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
    list_display = ['invoice_number', 'customer_name', 'item_count_display', 'total_display', 'payment_received', 'payment_method', 'created_at', 'invoice_button']
    list_filter = ['payment_received', 'payment_method', 'created_at']
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
        ('Payment', {
            'fields': ('shipping_cost', 'discount_percent', 'payment_received', 'payment_method', 'totals_display')
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
        pull_sheet_url = reverse('admin:manual-invoice-pull-sheet', args=[obj.pk])
        email_confirm_target = obj.customer_email or 'this customer (no email on file)'
        return format_html(
            '''<div style="display:flex;gap:6px;flex-wrap:wrap;white-space:nowrap">
                <a href="{}" target="_blank" style="background:#ff6b35;color:#fff;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;display:inline-block">🖨 Pull Sheet</a>
                <a href="{}" target="_blank" style="background:#1a1a24;color:#fff;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;border:1px solid #555;display:inline-block">📄 Print / View</a>
                <a href="{}" target="_blank" style="background:#ff6b35;color:#fff;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;display:inline-block">⬇ PDF</a>
                <a href="{}" onclick="return confirm('Email this invoice to {}? This will send a real email.')" style="background:#2e7d32;color:#fff;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;display:inline-block">✉️ Email</a>
            </div>''',
            pull_sheet_url, print_url, pdf_url, email_url, email_confirm_target
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
            path('<int:pk>/manual-invoice-pull-sheet/', self.admin_site.admin_view(self.pull_sheet_view), name='manual-invoice-pull-sheet'),
            path('pos/', self.admin_site.admin_view(self.pos_view), name='manual-invoice-pos'),
            path('pos/search/', self.admin_site.admin_view(self.pos_search_view), name='manual-invoice-pos-search'),
            path('pos/save/', self.admin_site.admin_view(self.pos_save_view), name='manual-invoice-pos-save'),
        ]
        return custom + super().get_urls()

    def print_invoice_view(self, request, pk):
        invoice = get_object_or_404(ManualInvoice, pk=pk)
        html = build_manual_invoice_html(invoice, show_controls=True)
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    def pull_sheet_view(self, request, pk):
        invoice = get_object_or_404(ManualInvoice, pk=pk)
        html = build_manual_invoice_pull_sheet_html(invoice, show_controls=True)
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
        ok, detail = _send_manual_invoice_email(invoice)
        if ok:
            messages.success(request, f"{invoice.invoice_number} {detail}")
        else:
            messages.error(request, f"{invoice.invoice_number}: {detail}")
        return redirect(reverse('admin:orders_manualinvoice_change', args=[invoice.pk]))

    def pos_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        csrf_token = get_token(request)
        search_url = reverse('admin:manual-invoice-pos-search')
        # Reuses products app's existing /api/sets/ endpoint (name="sets-list")
        # rather than maintaining a second, duplicate sets listing -- it's
        # already filtered to sets that actually have products and carries
        # logo/symbol URLs for later use.
        sets_url = reverse('sets-list')
        save_url = reverse('admin:manual-invoice-pos-save')
        cancel_url = reverse('admin:orders_manualinvoice_changelist')
        html = build_pos_html(csrf_token, search_url, sets_url, save_url, cancel_url, VARIANT_CHOICES)
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    def pos_search_view(self, request):
        """Two modes, both hit the same endpoint:
        - Free-text search (term only): the original name/sku/set lookup,
          capped at 30 results, newest set first.
        - Set browse (set_code present): lists the whole set (optionally
          narrowed by a name term and/or variant), ordered like the Manage
          Set screen (card_number, variant_sort, name) so staff can browse
          and bulk-add every card in a set for a bundle sale without typing
          each name individually. Capped higher since a full set can run
          into the hundreds of cards.

        Both modes filter to condition='NM' -- PokemonProduct can hold
        multiple rows per physical card (NM/LP/MP/HP/DMG, see
        stock_add_played), so without this filter a set browse would show
        duplicate cards and "Add all" would double them up. Mirrors the
        same condition='NM' filter card_search already applies for PoBuSA."""
        if not self.has_add_permission(request):
            raise PermissionDenied

        term = request.GET.get('term', '').strip()
        set_code = request.GET.get('set_code', '').strip()
        variant = request.GET.get('variant', '').strip()

        if not set_code and len(term) < 2:
            return JsonResponse({'results': []})

        products = PokemonProduct.objects.select_related('card_set').filter(condition='NM')

        if set_code:
            products = products.filter(card_set__code=set_code)
            if term:
                products = products.filter(name__icontains=term)
            if variant:
                products = products.filter(variant_override=variant)
            products = products.order_by('card_number', 'variant_sort', 'name')[:500]
        else:
            products = products.filter(
                Q(name__icontains=term) | Q(sku__icontains=term) |
                Q(card_set__name__icontains=term) | Q(card_set__code__icontains=term)
            )
            if variant:
                products = products.filter(variant_override=variant)
            products = products.order_by('-card_set__release_date', 'name')[:30]

        results = [{
            'id': p.id,
            'name': p.name,
            'set_name': p.card_set.name if p.card_set else '',
            'set_code': p.card_set.code if p.card_set else '',
            'card_number': p.card_number or '',
            'variant': p.variant_override or '',
            'price': float(p.price or 0),
            'stock': p.stock,
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

        payment_method = payload.get('payment_method') or ''
        if payment_method not in ('eft', 'cash', 'card'):
            payment_method = ''

        # Michael, 2026-08-02: "is automatic, when i save invoice? with BCC
        # to enquiries?" -- yes now. The invoice + line items are wrapped in
        # one atomic block, and the confirmation email (same content/BCC as
        # the manual "Email" button) is queued with transaction.on_commit so
        # it can only fire once everything is actually saved -- same fix as
        # CheckoutView's order-confirmation email, so this can't repeat the
        # "email sent but nothing in the DB" bug that hit Deon Becker's
        # order. The manual Email button still works too, for re-sends or
        # invoices created without an email on file at the time.
        email_result = {}

        with transaction.atomic():
            invoice = ManualInvoice.objects.create(
                customer_name=customer_name,
                customer_email=(payload.get('customer_email') or '').strip(),
                customer_phone=(payload.get('customer_phone') or '').strip(),
                delivery_note=(payload.get('delivery_note') or '').strip(),
                shipping_cost=shipping_cost,
                discount_percent=discount_percent,
                payment_received=bool(payload.get('payment_received')),
                payment_method=payment_method,
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

            def _fire_confirmation_email():
                ok, detail = _send_manual_invoice_email(invoice)
                email_result['sent'] = ok
                email_result['detail'] = detail
                # The JSON response's email_sent/email_detail fields (below)
                # weren't actually being read anywhere in the POS screen's
                # JS -- it just redirects on success and never looked at
                # them, so a failed send was invisible. Queuing a proper
                # Django admin message here means it shows as a banner on
                # the invoice's change page the moment the redirect lands,
                # same place the manual Email button's result already shows.
                if ok:
                    messages.success(request, f"{invoice.invoice_number} {detail}")
                else:
                    messages.error(request, f"{invoice.invoice_number}: {detail}")
            transaction.on_commit(_fire_confirmation_email)

        return JsonResponse({
            'success': True,
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'redirect_url': reverse('admin:orders_manualinvoice_change', args=[invoice.pk]),
            'email_sent': email_result.get('sent', False),
            'email_detail': email_result.get('detail', ''),
        })


# =============================================================================
# BUY ORDER — recording cards bought FROM a customer. Deliberately has no
# custom in-admin POS creation screen (unlike ManualInvoice's pos_view) --
# the standalone POS app (pos.pokebulk.co.za) is the intended entry point
# for creating these day to day. This admin registration exists so past buy
# orders can be reviewed, searched, and hand-edited if needed, and so the
# POS app has a save endpoint (pos_buy_save_view below) to call.
# =============================================================================

class BuyOrderItemInline(admin.TabularInline):
    model = BuyOrderItem
    extra = 3
    autocomplete_fields = ['product']
    fields = ['product', 'description', 'set_name', 'card_number', 'variant', 'quantity', 'unit_price', 'line_total_display']
    readonly_fields = ['line_total_display']

    def line_total_display(self, obj):
        if obj and obj.pk:
            return f"R {obj.line_total:.2f}"
        return "-"
    line_total_display.short_description = 'Line Total'


@admin.register(BuyOrder)
class BuyOrderAdmin(admin.ModelAdmin):
    list_display = ['buy_number', 'seller_name', 'item_count_display', 'total_display', 'payment_made', 'payment_method', 'created_at', 'buy_order_button']
    list_filter = ['payment_made', 'payment_method', 'created_at']
    search_fields = ['buy_number', 'seller_name', 'seller_email']
    readonly_fields = ['buy_number', 'created_at', 'updated_at', 'total_display', 'buy_order_button']
    ordering = ['-created_at']
    inlines = [BuyOrderItemInline]

    fieldsets = (
        ('Buy Order', {
            'fields': ('buy_number', 'created_at', 'updated_at', 'buy_order_button')
        }),
        ('Seller', {
            'fields': ('seller_name', 'seller_email', 'seller_phone', 'seller_note')
        }),
        ('Payment', {
            'fields': ('payment_made', 'payment_method', 'total_display')
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
    total_display.short_description = 'Total Paid'

    def buy_order_button(self, obj):
        if not obj.pk:
            return '-'
        print_url = reverse('admin:buy-order-print', args=[obj.pk])
        pdf_url = reverse('admin:buy-order-pdf', args=[obj.pk])
        email_url = reverse('admin:buy-order-email', args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank">Print</a> &nbsp;|&nbsp; '
            '<a href="{}">PDF</a> &nbsp;|&nbsp; '
            '<a href="{}" onclick="return confirm(\'Email this receipt to the seller?\')">Email</a>',
            print_url, pdf_url, email_url,
        )
    buy_order_button.short_description = 'Actions'

    def get_urls(self):
        custom = [
            path('pos-buy/save/', self.admin_site.admin_view(self.pos_buy_save_view), name='buy-order-pos-save'),
            path('<int:pk>/buy-order-print/', self.admin_site.admin_view(self.buy_order_print_view), name='buy-order-print'),
            path('<int:pk>/buy-order-pdf/', self.admin_site.admin_view(self.buy_order_pdf_view), name='buy-order-pdf'),
            path('<int:pk>/buy-order-email/', self.admin_site.admin_view(self.buy_order_email_view), name='buy-order-email'),
        ]
        return custom + super().get_urls()

    def buy_order_print_view(self, request, pk):
        buy_order = get_object_or_404(BuyOrder, pk=pk)
        html = build_buy_order_html(buy_order, show_controls=True)
        return HttpResponse(html)

    def buy_order_pdf_view(self, request, pk):
        buy_order = get_object_or_404(BuyOrder, pk=pk)
        html = build_buy_order_html(buy_order, show_controls=False)
        pdf_bytes = buy_order_html_to_pdf(html)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{buy_order.buy_number}.pdf"'
        return response

    def buy_order_email_view(self, request, pk):
        buy_order = get_object_or_404(BuyOrder, pk=pk)
        change_url = reverse('admin:orders_buyorder_change', args=[pk])

        if not buy_order.seller_email:
            self.message_user(request, "No seller email on file for this buy order.", level=messages.ERROR)
            return redirect(change_url)

        html = build_buy_order_html(buy_order, show_controls=False)
        pdf_bytes = buy_order_html_to_pdf(html)

        email = EmailMultiAlternatives(
            subject=f"Your buy-in receipt {buy_order.buy_number} - PokeBulk SA",
            body=strip_tags(html),
            to=[buy_order.seller_email],
            bcc=['enquiries@pokebulk.co.za'],
        )
        email.attach_alternative(html, "text/html")
        email.attach(f"{buy_order.buy_number}.pdf", pdf_bytes, 'application/pdf')

        try:
            email.send(fail_silently=False)
        except Exception as e:
            self.message_user(request, f"Could not send email: {e}", level=messages.ERROR)
            return redirect(change_url)

        self.message_user(request, f"Receipt emailed to {buy_order.seller_email}.")
        return redirect(change_url)

    def pos_buy_save_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid request body'}, status=400)

        seller_name = (payload.get('seller_name') or '').strip()
        items = payload.get('items') or []

        if not seller_name:
            return JsonResponse({'success': False, 'error': 'Seller name is required.'}, status=400)
        if not items:
            return JsonResponse({'success': False, 'error': 'At least one item is required.'}, status=400)

        payment_method = payload.get('payment_method') or ''
        if payment_method not in ('eft', 'cash', 'card'):
            payment_method = ''

        buy_order = BuyOrder.objects.create(
            seller_name=seller_name,
            seller_email=(payload.get('seller_email') or '').strip(),
            seller_phone=(payload.get('seller_phone') or '').strip(),
            internal_note=(payload.get('internal_note') or '').strip(),
            payment_made=bool(payload.get('payment_made')),
            payment_method=payment_method,
            created_by=request.user,
        )

        for item in items:
            product = None
            product_id = item.get('product_id')
            if product_id:
                product = PokemonProduct.objects.filter(pk=product_id).first()

            try:
                unit_price = Decimal(str(item.get('unit_price'))) if item.get('unit_price') is not None else Decimal('0.00')
            except (InvalidOperation, ValueError):
                unit_price = Decimal('0.00')

            try:
                quantity = max(1, int(item.get('quantity') or 1))
            except (ValueError, TypeError):
                quantity = 1

            BuyOrderItem.objects.create(
                buy_order=buy_order,
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
            'buy_id': buy_order.id,
            'buy_number': buy_order.buy_number,
        })
