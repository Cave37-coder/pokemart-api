"""
store_credit/models.py -- customer store credit ledger (2026-10-27).

Michael: "build in store credit across the full invoicing system, using the
Buy-in to select input to 'Store Credit', then show it when customers are
buying they can use the credit!" Rules he set:
  * credit always belongs to a site account (User);
  * issued from a Buying invoice (all or part of the payout), no bonus --
    R1 payout = R1 credit;
  * spent on website orders AND Manual Invoices; covers as much of the total
    as it can, any balance is paid by a normal method, and leftover credit
    simply stays on the account.

Design: an append-only ledger. A customer's balance is the SUM of their
transactions -- there is no separate balance column that could drift out of
sync. Every movement is one row: positive = credit in, negative = credit
out. Rows are linked to the BuyOrder / Order / ManualInvoice that caused
them, so "how much credit is on this order right now" is also just a SUM
(see services.py). Rows are never edited or deleted; a correction is a new
row (an admin "Manual adjustment").
"""
from django.conf import settings
from django.db import models


class StoreCreditTransaction(models.Model):
    KIND_CHOICES = [
        ('buyin', 'Buy-in payout'),
        ('buyin_reversal', 'Buy-in payout reversed'),
        ('order', 'Spent on website order'),
        ('order_refund', 'Website order credit refunded'),
        ('invoice', 'Spent on manual invoice'),
        ('invoice_refund', 'Manual invoice credit refunded'),
        ('adjustment', 'Manual adjustment'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='store_credit_transactions',
        help_text='Customer account the credit belongs to.',
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Positive = credit added, negative = credit used.',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='adjustment')
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    buy_order = models.ForeignKey('orders.BuyOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='store_credit_transactions')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='store_credit_transactions')
    manual_invoice = models.ForeignKey('orders.ManualInvoice', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='store_credit_transactions')

    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Store credit transaction'
        indexes = [models.Index(fields=['user', 'created_at'], name='storecredit_user_created_idx')]

    def __str__(self):
        sign = '+' if self.amount >= 0 else '-'
        return f'{self.user} {sign}R{abs(self.amount)} ({self.get_kind_display()})'

    @property
    def reference(self):
        if self.buy_order_id:
            return self.buy_order.buy_number if self.buy_order else ''
        if self.order_id:
            return f'Order #{self.order_id}'
        if self.manual_invoice_id:
            return self.manual_invoice.invoice_number if self.manual_invoice else ''
        return ''
