"""
store_credit/services.py -- the ONLY place credit is moved (2026-10-27).

Every function locks the customer's User row (SELECT ... FOR UPDATE) first,
so two things spending the same credit at the same moment (e.g. a website
checkout while a Manual Invoice is saved) are serialised and can never take
the balance below zero. Call these inside a transaction (they open one if
the caller hasn't).

"Applied" amounts are always derived from the ledger itself:
    issued on a buy-in  = SUM(amount) of rows linked to that BuyOrder
    used on an order    = -SUM(amount) of rows linked to that Order
so reconciling to a new target is just "post the difference".
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum

from .models import StoreCreditTransaction

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


class StoreCreditError(ValueError):
    """User-facing problem (insufficient credit, already spent, ...)."""


def _q(v):
    return (Decimal(str(v or 0))).quantize(CENT)


def balance(user):
    """Current credit balance for `user` (a User or a user id). 0 for none."""
    if user is None:
        return ZERO
    uid = getattr(user, 'pk', user)
    total = StoreCreditTransaction.objects.filter(user_id=uid).aggregate(s=Sum('amount'))['s']
    return _q(total)


def _lock_user(uid):
    get_user_model().objects.select_for_update().filter(pk=uid).values_list('pk', flat=True).first()


def _post(uid, amount, kind, note='', created_by=None, **links):
    """Write one ledger row (amount != 0) with balance_after. Caller holds the lock."""
    amount = _q(amount)
    if amount == 0:
        return None
    new_balance = balance(uid) + amount
    if new_balance < 0:
        raise StoreCreditError(
            f'Not enough store credit: balance is R{balance(uid)}, needs R{-amount}.')
    return StoreCreditTransaction.objects.create(
        user_id=uid, amount=amount, kind=kind, balance_after=new_balance,
        note=note[:255], created_by=created_by, **links)


def linked_total(**link):
    """Signed SUM of all ledger rows linked to one document, e.g.
    linked_total(order=o). Spends are negative, payouts positive."""
    return _q(StoreCreditTransaction.objects.filter(**link).aggregate(s=Sum('amount'))['s'])


def linked_user_id(**link):
    row = StoreCreditTransaction.objects.filter(**link).order_by('-id').values_list('user_id', flat=True).first()
    return row


# ---------------------------------------------------------------- adjustments

def adjust(user, amount, note='', created_by=None):
    """Manual +/- correction by staff."""
    uid = getattr(user, 'pk', user)
    with transaction.atomic():
        _lock_user(uid)
        return _post(uid, amount, 'adjustment', note=note or 'Manual adjustment', created_by=created_by)


# ---------------------------------------------------------------- buy-ins

def set_buyin_credit(buy_order, target, created_by=None):
    """Make the credit issued by `buy_order` equal `target` (>= 0). Paying
    out posts +; reversing (un-pay / cancel) posts -, which fails with
    StoreCreditError if the customer has already spent it. Returns the
    amount now issued."""
    target = _q(target)
    with transaction.atomic():
        issued_uid = linked_user_id(buy_order=buy_order)
        # Credit already issued to a different account (seller link changed):
        # take it back from that account first.
        if issued_uid and issued_uid != buy_order.user_id:
            _lock_user(issued_uid)
            back = linked_total(buy_order=buy_order)
            if back:
                _post(issued_uid, -back, 'buyin_reversal', note=f'{buy_order.buy_number} moved to another account',
                      created_by=created_by, buy_order=buy_order)
        if target > 0 and not buy_order.user_id:
            raise StoreCreditError('Link the seller to their site account before paying out store credit.')
        if not buy_order.user_id:
            return ZERO
        uid = buy_order.user_id
        _lock_user(uid)
        current = _q(StoreCreditTransaction.objects.filter(buy_order=buy_order, user_id=uid)
                     .aggregate(s=Sum('amount'))['s'])
        delta = target - current
        if delta > 0:
            _post(uid, delta, 'buyin', note=f'Paid out on {buy_order.buy_number}', created_by=created_by,
                  buy_order=buy_order)
        elif delta < 0:
            try:
                _post(uid, delta, 'buyin_reversal', note=f'{buy_order.buy_number} reversed', created_by=created_by,
                      buy_order=buy_order)
            except StoreCreditError:
                raise StoreCreditError(
                    f'The customer has already used some of this credit (balance R{balance(uid)}, '
                    f'R{-delta} would need to come back). Adjust their credit manually first.')
        return target


# ---------------------------------------------------------------- spending

def _set_spent(link_name, doc, user_id, target, spend_kind, refund_kind, label, created_by=None, cap_to_balance=False):
    """Make the credit used on `doc` (an Order or ManualInvoice) equal
    `target`. Refunds go back to whichever account paid them. With
    cap_to_balance, a target bigger than what's available is reduced to the
    most that can be taken instead of failing. Returns the amount now used."""
    target = _q(target)
    if target < 0:
        target = ZERO
    link = {link_name: doc}
    with transaction.atomic():
        paid_uid = linked_user_id(**link)
        if paid_uid and paid_uid != user_id:
            _lock_user(paid_uid)
            used_by_other = -linked_total(**link)
            if used_by_other > 0:
                _post(paid_uid, used_by_other, refund_kind, note=f'{label}: customer changed',
                      created_by=created_by, **link)
        if not user_id:
            if target > 0:
                raise StoreCreditError('Link the customer to their site account to use store credit.')
            return ZERO
        _lock_user(user_id)
        current = -_q(StoreCreditTransaction.objects.filter(user_id=user_id, **link)
                      .aggregate(s=Sum('amount'))['s'])
        delta = target - current
        if delta > 0 and cap_to_balance:
            delta = min(delta, balance(user_id))
        if delta > 0:
            _post(user_id, -delta, spend_kind, note=f'Used on {label}', created_by=created_by, **link)
        elif delta < 0:
            _post(user_id, -delta, refund_kind, note=f'{label}: credit returned', created_by=created_by, **link)
        return current + delta


def set_order_credit(order, target, created_by=None, cap_to_balance=False):
    return _set_spent('order', order, order.user_id, target, 'order', 'order_refund',
                      f'Order #{order.pk}', created_by, cap_to_balance)


def set_invoice_credit(invoice, target, created_by=None, cap_to_balance=False):
    return _set_spent('manual_invoice', invoice, invoice.user_id, target, 'invoice', 'invoice_refund',
                      invoice.invoice_number or 'manual invoice', created_by, cap_to_balance)
