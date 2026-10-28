"""
pudo.py -- Pudo (The Courier Guy Locker) API client: locker list, locker-to-locker bookings, waybills.

Michael, 2026-10-28: "Pudo has an API built in, so we can trigger automated Locker bookings ... when I move
status to 'Courier Being Booked' it automatically triggers the parcel being booked and we add the Waybill
to the order."

Docs: https://api-pudo.co.za/ (production) and https://dev.api-pudo.co.za/ (dev). Endpoints used:
    GET  /lockers-data            locker / kiosk list (code like "CG54")
    POST /rates                   {"collection_address": {"terminal_id"}, "delivery_address": {"terminal_id"}}
    POST /shipments               create the L2L shipment -> id, custom_tracking_reference (waybill), pincode
    GET  /generate/waybill/<id>   signed PDF url
    PUT  /shipments/<id>          {"status": "cancelled"}

Settings (Railway environment variables) -- nothing is hard-coded and booking is OFF unless switched on:
    PUDO_BOOKING_ENABLED   "1" to book automatically (anything else = off, status changes work as before)
    PUDO_API_KEY           your Pudo API key
    PUDO_API_BASE          default https://api-tcg.co.za/api/v1 (live). For a sandbox account use https://sandbox.api-pudo.co.za/api/v1.
                           NOTE the /api/v1 -- without it every route 404s ("The route rates could not be found").
    PUDO_AUTH_HEADER       default "Authorization"   (header NAME the key is sent in)
    PUDO_AUTH_PREFIX       default "Bearer "         (text put before the key; "" for a bare key)
    PUDO_SENDER_TERMINAL   the locker YOU drop parcels at (code like "CG54")
    PUDO_SENDER_NAME / PUDO_SENDER_EMAIL / PUDO_SENDER_MOBILE   sender contact on every booking
    PUDO_TRACKING_URL      optional, e.g. "https://.../track?ref={waybill}" -- stored on the order if set
"""
import logging
import os
import re
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)

LOCKER_METHODS = ('pudo_locker', 'pudo_kiosk', 'pudo_medium')
TIMEOUT = 25


class PudoError(Exception):
    """Anything that stops a booking; the message is shown to staff as-is."""


def _env(name, default=''):
    return getattr(settings, name, None) or os.environ.get(name) or default


def enabled():
    return str(_env('PUDO_BOOKING_ENABLED', '')).strip().lower() in ('1', 'true', 'yes', 'on')


def _base():
    return str(_env('PUDO_API_BASE', 'https://api-tcg.co.za/api/v1')).rstrip('/')


def _headers():
    key = str(_env('PUDO_API_KEY', '')).strip()
    if not key:
        raise PudoError('PUDO_API_KEY is not set on the server.')
    return {
        str(_env('PUDO_AUTH_HEADER', 'Authorization')): f"{_env('PUDO_AUTH_PREFIX', 'Bearer ')}{key}",
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def _call(method, path, **kw):
    url = f'{_base()}{path}'
    try:
        resp = requests.request(method, url, headers=_headers(), timeout=TIMEOUT, **kw)
    except requests.RequestException as e:
        raise PudoError(f'Could not reach Pudo ({e.__class__.__name__}).')
    try:
        data = resp.json()
    except ValueError:
        data = {'raw': resp.text[:300]}
    if resp.status_code >= 400:
        msg = ''
        if isinstance(data, dict):
            msg = data.get('message') or data.get('error') or data.get('detail') or str(data)[:300]
        raise PudoError(f'Pudo said {resp.status_code}: {msg}')
    return data


# ---------------------------------------------------------------- lockers --------------------------
def get_lockers():
    """Full locker/kiosk list, cached 12h (and a 30-day stale copy kept as a fallback when Pudo's
    /lockers-data errors -- it returned HTTP 500 on 2026-10-28 while /rates worked).
    [{code, name, address, town, postal, type}]"""
    cached = cache.get('pudo_lockers_v1')
    if cached is not None:
        return cached
    raw, last = None, None
    for attempt in range(3):
        try:
            raw = _call('GET', '/lockers-data')
            break
        except PudoError as e:
            last = e
            if 'Pudo said 5' not in str(e) and 'Could not reach' not in str(e):
                raise
            time.sleep(2)
    if raw is None:
        stale = cache.get('pudo_lockers_stale_v1')
        if stale:
            return stale
        raise last
    if isinstance(raw, dict):
        raw = raw.get('data') or raw.get('lockers') or []
    out = []
    for r in raw:
        place = r.get('place') or {}
        detail = r.get('detailed_address') or {}
        out.append({
            'code': r.get('code') or '',
            'name': r.get('name') or '',
            'address': r.get('address') or '',
            'town': detail.get('locality') or place.get('town') or '',
            'postal': detail.get('postal_code') or place.get('postalCode') or '',
            'type': (r.get('type') or {}).get('name') or '',
        })
    out = [r for r in out if r['code']]
    cache.set('pudo_lockers_v1', out, 60 * 60 * 12)
    cache.set('pudo_lockers_stale_v1', out, 60 * 60 * 24 * 30)
    return out


def search_lockers(q, limit=15):
    q = (q or '').strip().lower()
    if len(q) < 2:
        return []
    words = q.split()
    hits = []
    for r in get_lockers():
        hay = f"{r['code']} {r['name']} {r['address']} {r['town']} {r['postal']}".lower()
        if all(w in hay for w in words):
            # exact code / name-prefix matches first
            score = 0 if r['code'].lower() == q else (1 if r['name'].lower().startswith(q) else 2)
            hits.append((score, r['name'], r))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [h[2] for h in hits[:limit]]


def locker_by_code(code):
    code = (code or '').strip().upper()
    return next((r for r in get_lockers() if r['code'].upper() == code), None)


# ---------------------------------------------------------------- booking --------------------------
def _mobile(raw):
    digits = re.sub(r'\D', '', raw or '')
    if digits.startswith('27'):
        return '+' + digits
    if digits.startswith('0'):
        return '+27' + digits[1:]
    return '+27' + digits if digits else ''


# Parcel size by card count lives in orders/shipping.py (shared with checkout pricing and the pull sheet):
# 1-600 cards = Extra Small, then one size up for every further 600. Medium/Tins is never smaller than Medium.
from . import shipping as _shipping

SIZES = [n.lower() for n in _shipping.SIZE_NAMES]
SIZE_SHORT = _shipping.SIZE_SHORT


def cards_per_size():
    return _shipping.cards_per_size()


def parcel_tier(order):
    """(tier index 0..4, card count) for an order."""
    n = sum(i.quantity for i in order.items.all())
    if n > _shipping.max_cards():
        raise PudoError(f'{n} cards is more than one parcel ({_shipping.max_cards()} max) - split it or book on Pudo yourself.')
    return _shipping.tier_for(n, order.shipping_method), n


def _is_size(want, service_name):
    name = (service_name or '').lower()
    if want == 'small':
        return 'small' in name and 'extra' not in name
    if want == 'large':
        return 'large' in name and 'extra' not in name
    return want in name


def _service_for(tier, sender, receiver):
    """Ask Pudo for the L2L rates and pick the service level for this size tier."""
    data = _call('POST', '/rates', json={'collection_address': {'terminal_id': sender},
                                         'delivery_address': {'terminal_id': receiver}})
    rates = data.get('rates') if isinstance(data, dict) else None
    if not rates:
        raise PudoError('Pudo returned no rates for that locker pair.')
    want = SIZES[tier]
    for r in rates:
        sl = r.get('service_level') or {}
        if (r.get('can_book') or {}).get('status') is False:
            continue
        if _is_size(want, sl.get('name')) and sl.get('code'):
            return sl['code'], r.get('rate')
    names = ', '.join((r.get('service_level') or {}).get('name', '?') for r in rates)
    raise PudoError(f'No "{want}" parcel size offered for that route (got: {names}).')


def book_order(order):
    """Create the locker-to-locker shipment for `order` and return
    {'shipment_id','waybill','pin','rate','service'}. Raises PudoError with a human-readable reason."""
    if order.shipping_method not in LOCKER_METHODS:
        raise PudoError('Only Pudo locker / kiosk / medium orders can be booked automatically.')
    receiver = (order.pudo_locker_code or '').strip().upper()
    if not receiver:
        raise PudoError('This order has no Pudo locker code. Pick the locker (Manage > Change delivery) first.')
    sender = str(_env('PUDO_SENDER_TERMINAL', '')).strip().upper()
    if not sender:
        raise PudoError('PUDO_SENDER_TERMINAL (your drop-off locker code) is not set on the server.')

    user = order.user
    rname = (f'{user.first_name} {user.last_name}'.strip() or user.username)
    rmobile = _mobile(getattr(user, 'phone_number', ''))
    if not rmobile:
        raise PudoError("The customer has no cell number on their profile (Pudo needs it for the locker PIN).")

    tier, n_cards = parcel_tier(order)
    code, rate = _service_for(tier, sender, receiver)
    body = {
        'collection_address': {'terminal_id': sender},
        'collection_contact': {
            'name': str(_env('PUDO_SENDER_NAME', 'PokeBulk SA')),
            'email': str(_env('PUDO_SENDER_EMAIL', 'enquiries@pokebulk.co.za')),
            'mobile_number': _mobile(str(_env('PUDO_SENDER_MOBILE', ''))),
        },
        'special_instructions_collection': f'PokeBulk order #{order.id} - {n_cards} cards',
        'delivery_address': {'terminal_id': receiver},
        'delivery_contact': {'name': rname, 'email': user.email or '', 'mobile_number': rmobile},
        'service_level_code': code,
        'collection_min_date': (timezone.now() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
    }
    data = _call('POST', '/shipments', json=body)
    if not isinstance(data, dict) or not data.get('id'):
        raise PudoError(f'Unexpected reply from Pudo: {str(data)[:200]}')
    waybill = data.get('custom_tracking_reference') or ''
    if not waybill:
        raise PudoError('Pudo accepted the booking but sent no waybill number (shipment id %s).' % data.get('id'))
    return {
        'shipment_id': str(data['id']),
        'waybill': waybill,
        'pin': str(data.get('pincode') or ''),
        'rate': data.get('rate') or rate,
        'service': data.get('service_level_name') or code,
    }


def apply_booking(order, result):
    """Write a booking result onto the (unsaved) order so the status email carries the waybill."""
    order.waybill_number = result['waybill']
    order.courier_name = 'Pudo'
    order.pudo_shipment_id = result['shipment_id']
    order.pudo_pin = result['pin']
    order.pudo_booked_at = timezone.now()
    order.pudo_booking_error = ''
    tpl = str(_env('PUDO_TRACKING_URL', '')).strip()
    if tpl:
        order.courier_tracking_url = tpl.replace('{waybill}', result['waybill'])


def waybill_pdf_url(shipment_id):
    data = _call('GET', f'/generate/waybill/{shipment_id}')
    if isinstance(data, dict):
        return data.get('url') or data.get('signed_url') or data.get('data') or ''
    return str(data or '')


def cancel_shipment(shipment_id):
    _call('PUT', f'/shipments/{shipment_id}', json={'status': 'cancelled'})
