"""Collection scheduling + Pudo send days (2026-10-30).

Michael's rules:
  * Collection customers pick a date at checkout -- nothing earlier than
    2 days after the order, and when the preparation time is longer the
    earliest date moves out to its upper figure ("push to 4 days, for
    earliest date then to match standard time"). Anyone needing it sooner
    WhatsApps Michael before ordering.
  * Collection hours: weekdays 18:15-20:30, weekends 10:00-16:00.
  * Days booked to an event / Gengar Games (CalendarEvent, Django admin)
    are closed for collection.
  * Or the customer ticks "No Rush" instead of picking a date.
  * Pudo: KZN + Eastern Cape parcels go Monday-Thursday only (never Friday --
    weekend in a warehouse). Western Cape: Mon, Tue, Wed and Fri, never
    Thursday. Other provinces: any weekday (assumed -- not specified).
"""
import re
from datetime import date, timedelta

from django.utils import timezone

MIN_LEAD_DAYS = 2
BOOKING_WINDOW_DAYS = 60
WHATSAPP_NUMBER = "074 488 6919"
WHATSAPP_LINK = "https://wa.me/27744886919"

WEEKDAY_HOURS = ("18:15", "20:30")
WEEKEND_HOURS = ("10:00", "16:00")


def collection_hours(d):
    return WEEKEND_HOURS if d.weekday() >= 5 else WEEKDAY_HOURS


def lead_days():
    from . import prep_time
    try:
        high = prep_time.current().display_range()[1]
    except Exception:
        high = 0
    return max(MIN_LEAD_DAYS, high)


def earliest_collection_date(today=None):
    today = today or timezone.localdate()
    return today + timedelta(days=lead_days())


def blocking_events(start, end):
    """{date: [CalendarEvent, ...]} for every day in start..end closed for collection."""
    from .models import CalendarEvent
    out = {}
    evs = CalendarEvent.objects.filter(blocks_collection=True, start_date__lte=end).exclude(
        end_date__lt=start)
    for ev in evs:
        last = ev.end_date or ev.start_date
        d = max(ev.start_date, start)
        while d <= min(last, end):
            out.setdefault(d, []).append(ev)
            d += timedelta(days=1)
    return out


def collection_days(today=None, window=BOOKING_WINDOW_DAYS):
    """Every day from today for `window` days with whether it can be picked."""
    today = today or timezone.localdate()
    earliest = earliest_collection_date(today)
    end = today + timedelta(days=window)
    blocked = blocking_events(today, end)
    days = []
    d = today
    while d <= end:
        hrs = collection_hours(d)
        evs = blocked.get(d, [])
        if evs:
            reason = "; ".join(e.title for e in evs)
        elif d < earliest:
            reason = "too_soon"
        else:
            reason = ""
        days.append({
            "date": d.isoformat(),
            "open": not reason,
            "hours": f"{hrs[0]}–{hrs[1]}",
            "reason": reason,
        })
        d += timedelta(days=1)
    return earliest, days


def validate_collection_date(value, today=None):
    """Returns (date, None) if `value` (YYYY-MM-DD) can be booked, else (None, error)."""
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None, "Please choose a valid collection date."
    today = today or timezone.localdate()
    earliest = earliest_collection_date(today)
    if d < earliest:
        return None, (f"The earliest collection date is {earliest:%a %d %b}. "
                      f"Need it sooner? WhatsApp Michael on {WHATSAPP_NUMBER} first.")
    if d > today + timedelta(days=BOOKING_WINDOW_DAYS):
        return None, "Please choose a collection date within the next two months."
    evs = blocking_events(d, d).get(d)
    if evs:
        return None, f"Sorry, we're not available for collections on {d:%a %d %b} ({evs[0].title}). Please choose another day."
    return d, None


# --- Pudo send days ---------------------------------------------------------

_REGIONS = [
    ("KZN", re.compile(r"kwa-?zulu|\bkzn\b|natal|durban|pietermaritzburg|umhlanga|ballito|pinetown|"
                       r"richards bay|newcastle|amanzimtoti|westville|hillcrest|umlazi|ladysmith|port shepstone|empangeni", re.I)),
    ("EC", re.compile(r"eastern cape|port elizabeth|gqeberha|east london|mthatha|makhanda|grahamstown|"
                      r"jeffreys bay|jeffrey's bay|uitenhage|kariega|queenstown|komani|bhisho|king william", re.I)),
    ("WC", re.compile(r"western cape|cape town|stellenbosch|paarl|george\b|somerset west|bellville|durbanville|"
                      r"knysna|mossel bay|worcester|hermanus|strand\b|brackenfell|kuils river|table view|"
                      r"milnerton|claremont|plettenberg|oudtshoorn|malmesbury|wellington|gordon'?s bay", re.I)),
]

# Monday=0 ... Sunday=6
SEND_DAYS = {
    "KZN": (0, 1, 2, 3),
    "EC": (0, 1, 2, 3),
    "WC": (0, 1, 2, 4),
    "OTHER": (0, 1, 2, 3, 4),
}
REGION_LABELS = {"KZN": "KZN", "EC": "Eastern Cape", "WC": "Western Cape", "OTHER": "Other"}


def pudo_region(order):
    hay = " ".join(filter(None, [
        order.delivery_province, order.delivery_city, order.pudo_locker_address,
        order.pudo_locker_name, order.delivery_address_line2]))
    for code, rx in _REGIONS:
        if rx.search(hay):
            return code
    return "OTHER"


def next_send_day(order, today=None):
    """Next day (today included) this Pudo order may be sent, or None for collection orders."""
    if order.delivery_method == "collection" or order.shipping_method == "collection":
        return None
    today = today or timezone.localdate()
    allowed = SEND_DAYS[pudo_region(order)]
    d = today
    for _ in range(8):
        if d.weekday() in allowed:
            return d
        d += timedelta(days=1)
    return None
