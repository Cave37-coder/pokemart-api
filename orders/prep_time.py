"""Order preparation time estimate (2026-10-30).

Michael: "pull a order preparation time from the database and then have it
on the landing page and check out page, updated daily, so it allows
customers to have a realistic expectation" -- after a customer cancelled a
COC order because he hadn't heard anything for 5 days during a backlog.

How the figure is worked out (all from data we already store):

  start = when the order became "Order Confirmed" -- the first 'pending'
          OrderTracking row (EFT orders reach it once payment reflects),
          or created_at for orders that were created straight as 'pending'
          (COC) and so never got a 'pending' tracking row.
  end   = the first time the order reached a "prepared" status:
          ready (collection), booked / collected (Pudo) or invoiced.

Over the last LOOKBACK_DAYS of finished orders we take the median (typical)
and the 80th percentile (slow-but-normal). Then we look at the queue right
now: if the oldest open order has already been waiting longer than the
historical slow figure, the upper end moves up to match it -- so a backlog
week shows a longer time straight away instead of a week later.

Shown to customers as whole days, e.g. "2-4 days". "No Rush" orders are left out of both (they wait on purpose).
Refreshed daily by
`python manage.py update_prep_time` (railway.cron.toml) and also on demand
by the API when the stored figure is older than STALE_AFTER.
"""
import math
from datetime import timedelta

from django.utils import timezone

LOOKBACK_DAYS = 30
MIN_SAMPLE = 5                 # fewer finished orders than this -> use defaults
DEFAULT_RANGE = (2, 4)         # days, used until there's enough history
MAX_DAYS = 14                  # never show anything sillier than this
STALE_AFTER = timedelta(hours=26)

START_STATUS = 'pending'
PREPARED_STATUSES = ('ready', 'booked', 'collected', 'invoiced')
OPEN_STATUSES = ('pending', 'printed', 'packed')


def _percentile(sorted_vals, pct):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * pct
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _start_time(order, rows):
    for r in rows:
        if r.status == START_STATUS:
            return r.created_at
    return order.created_at


def compute():
    """Returns a dict of the numbers; does not save anything."""
    from .models import Order

    now = timezone.now()
    since = now - timedelta(days=LOOKBACK_DAYS)

    # --- finished orders: how long did they take? -------------------------
    durations = []
    finished = (Order.objects
                .filter(created_at__gte=since - timedelta(days=MAX_DAYS),
                        tracking__status__in=PREPARED_STATUSES, no_rush=False)
                .distinct()
                .prefetch_related('tracking'))
    for o in finished:
        rows = sorted(o.tracking.all(), key=lambda r: r.created_at)
        start = _start_time(o, rows)
        end = next((r.created_at for r in rows
                    if r.status in PREPARED_STATUSES and r.created_at >= start), None)
        if end is None or end < since:
            continue
        durations.append((end - start).total_seconds() / 86400)
    durations.sort()

    # --- the queue right now ---------------------------------------------
    # Only orders from the last MAX_DAYS count as "the queue", so one old
    # order left open by mistake can't push the estimate to the maximum.
    open_orders = list(Order.objects
                       .filter(status__in=OPEN_STATUSES, no_rush=False, created_at__gte=now - timedelta(days=MAX_DAYS))
                       .prefetch_related('tracking'))
    oldest_wait = 0.0
    for o in open_orders:
        rows = sorted(o.tracking.all(), key=lambda r: r.created_at)
        oldest_wait = max(oldest_wait, (now - _start_time(o, rows)).total_seconds() / 86400)

    if len(durations) >= MIN_SAMPLE:
        median = _percentile(durations, 0.5)
        p80 = _percentile(durations, 0.8)
        low = max(1, math.ceil(median))
        high = max(low + 1, math.ceil(p80), math.ceil(oldest_wait))
        source = 'history'
    else:
        median = p80 = None
        low, high = DEFAULT_RANGE
        high = max(high, math.ceil(oldest_wait))
        source = 'default'

    low, high = min(low, MAX_DAYS), min(high, MAX_DAYS)
    return {
        'low_days': low,
        'high_days': high,
        'median_days': round(median, 2) if median is not None else None,
        'p80_days': round(p80, 2) if p80 is not None else None,
        'sample_size': len(durations),
        'open_orders': len(open_orders),
        'oldest_open_days': round(oldest_wait, 2),
        'source': source,
    }


def refresh():
    """Compute and store today's figure. Returns the saved PrepTimeEstimate."""
    from .models import PrepTimeEstimate
    data = compute()
    est = PrepTimeEstimate.get()
    for k, v in data.items():
        setattr(est, k, v)
    est.computed_at = timezone.now()
    est.save()
    return est


def current():
    """The stored estimate, refreshed first if it's missing or stale."""
    from .models import PrepTimeEstimate
    est = PrepTimeEstimate.get()
    if est.computed_at is None or timezone.now() - est.computed_at > STALE_AFTER:
        est = refresh()
    return est
