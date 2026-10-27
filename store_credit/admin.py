from django import forms
from django.contrib import admin, messages
from django.db.models import Sum
from django.utils.html import format_html

from .models import StoreCreditTransaction
from . import services


class AdjustmentForm(forms.ModelForm):
    class Meta:
        model = StoreCreditTransaction
        fields = ['user', 'amount', 'note']
        help_texts = {
            'amount': 'Positive adds credit, negative removes it (e.g. -50.00).',
        }


@admin.register(StoreCreditTransaction)
class StoreCreditTransactionAdmin(admin.ModelAdmin):
    """The credit ledger. Rows are never edited or deleted -- to correct a
    balance, Add a new row ("Manual adjustment") with a + or - amount.
    Buy-in payouts / spends are written automatically by the Buying invoice,
    website checkout and Manual Invoice flows."""
    list_display = ['created_at', 'user', 'amount_display', 'kind', 'reference_display', 'balance_after', 'note', 'created_by']
    list_filter = ['kind', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'note',
                     'buy_order__buy_number', 'manual_invoice__invoice_number', '=order__id']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'
    list_select_related = ['user', 'buy_order', 'manual_invoice', 'created_by']

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = AdjustmentForm
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return [f.name for f in self.model._meta.fields]

    def has_change_permission(self, request, obj=None):
        # Viewing is allowed (read-only form); nothing can actually be changed.
        return obj is None or request.method in ('GET', 'HEAD')

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return
        try:
            row = services.adjust(obj.user, obj.amount, note=obj.note, created_by=request.user)
        except services.StoreCreditError as e:
            messages.error(request, str(e))
            return
        if row is not None:
            obj.pk = row.pk
            messages.success(request, f'{obj.user}: balance is now R{services.balance(obj.user)}.')

    def response_add(self, request, obj, post_url_continue=None):
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:store_credit_storecredittransaction_changelist'))

    @admin.display(description='Amount', ordering='amount')
    def amount_display(self, obj):
        color = '#2e7d32' if obj.amount >= 0 else '#c62828'
        sign = '+' if obj.amount >= 0 else '-'
        return format_html('<strong style="color:{}">{}R {}</strong>', color, sign, f'{abs(obj.amount):.2f}')

    @admin.display(description='Reference')
    def reference_display(self, obj):
        return obj.reference

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        total = StoreCreditTransaction.objects.aggregate(s=Sum('amount'))['s'] or 0
        extra_context['title'] = f'Store credit ledger -- total credit outstanding R {total:.2f}'
        return super().changelist_view(request, extra_context=extra_context)
