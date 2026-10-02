"""
Web Push sending (2026-10-02).

Everything that sends a push notification goes through here, so there is
one place that knows about VAPID keys, dead-subscription cleanup and the
"never break the caller" rule.

Same two rules as every email call site in this codebase
(orders/signals.py, community/views.py):
  1. A failed notification must NEVER break the thing that triggered it
     (saving an order status, sending a DM) -- everything is wrapped and
     logged instead of raised.
  2. Network calls run off-thread, so a slow push service can't stall a
     request (or PayFast's webhook) the way a slow MailerSend call once
     stalled checkout.

If the VAPID keys are not set in the environment, every function here is a
silent no-op -- the site keeps working exactly as before, it just sends no
pushes. Generate keys with:  python manage.py generate_vapid_keys
"""
import json
import logging
import threading
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

# The only hosts a real browser push subscription can point at. Checked at
# subscribe time (notifications/views.py) AND again here before sending:
# the endpoint comes from the customer's browser, so without this anyone
# logged in could register an arbitrary URL and make this server POST to
# it.
ALLOWED_PUSH_HOST_SUFFIXES = (
    'fcm.googleapis.com',            # Chrome, Edge, Samsung Internet, Opera (Android + desktop)
    'push.services.mozilla.com',     # Firefox
    'push.apple.com',                # Safari + iPhone/iPad home-screen apps
    'notify.windows.com',            # older Edge
)

# How long the push service keeps trying if the phone is off / offline.
PUSH_TTL_SECONDS = 60 * 60 * 24


def is_configured():
    return bool(getattr(settings, 'VAPID_PRIVATE_KEY', '') and getattr(settings, 'VAPID_PUBLIC_KEY', ''))


def is_allowed_endpoint(endpoint):
    try:
        parsed = urlparse(endpoint or '')
    except ValueError:
        return False
    if parsed.scheme != 'https' or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return any(host == s or host.endswith('.' + s) for s in ALLOWED_PUSH_HOST_SUFFIXES)


def send_push_to_user(user_id, title, body, url='/', tag=''):
    """Send one notification to every device this customer has turned
    notifications on for. Synchronous -- call send_push_async() from
    request/signal code instead. Returns the number of devices reached."""
    if not is_configured():
        return 0

    # Imported here, not at module level, so a missing/broken pywebpush
    # install can only ever cost push notifications -- never take down
    # orders/signals.py or community/views.py, which import this module.
    from pywebpush import webpush, WebPushException
    from .models import PushSubscription

    payload = json.dumps({'title': title, 'body': body, 'url': url, 'tag': tag})
    sent = 0
    for sub in PushSubscription.objects.filter(user_id=user_id):
        if not is_allowed_endpoint(sub.endpoint):
            sub.delete()
            continue
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                # A fresh dict every call on purpose: pywebpush writes the
                # per-push-service "aud" into whatever dict it is given, so
                # a shared one would carry Google's audience into the next
                # Apple request and get it rejected.
                vapid_claims={'sub': settings.VAPID_CLAIM_EMAIL},
                ttl=PUSH_TTL_SECONDS,
                timeout=10,
            )
            sent += 1
            PushSubscription.objects.filter(pk=sub.pk).update(last_success_at=timezone.now())
        except WebPushException as exc:
            status = getattr(exc.response, 'status_code', None)
            if status in (404, 410):
                # The push service is telling us this device is gone for
                # good (app removed, notifications switched off in phone
                # settings, browser data cleared). Not an error -- just
                # stop sending to it.
                logger.info("Push subscription %s expired (HTTP %s) -- removed.", sub.pk, status)
                sub.delete()
            else:
                logger.warning("Push to subscription %s failed (HTTP %s): %s", sub.pk, status, exc)
        except Exception:
            logger.exception("Push to subscription %s failed unexpectedly", sub.pk)
    return sent


def _run(user_id, title, body, url, tag):
    try:
        send_push_to_user(user_id, title, body, url=url, tag=tag)
    except Exception:
        logger.exception("Push notification thread failed for user_id=%s", user_id)
    finally:
        # This thread opened its own DB connection; Django only closes
        # connections automatically at the end of a *request*, so without
        # this each push would leak one.
        connection.close()


def send_push_async(user_id, title, body, url='/', tag=''):
    """Fire-and-forget. Safe to call from anywhere; never raises."""
    try:
        if not user_id or not is_configured():
            return
        threading.Thread(target=_run, args=(user_id, title, body, url, tag), daemon=True).start()
    except Exception:
        logger.exception("Could not start push notification thread for user_id=%s", user_id)


# ── The actual notifications the site sends ──────────────────────────────

def push_order_status(order):
    """Order status changed -- called from orders/signals.py right next to
    the status-update email, after the transaction has committed."""
    try:
        body = f"Status: {order.get_status_display()}"
        note = getattr(order, '_tracking_note', '') or ''
        if note:
            body += f"\n{note[:140]}"
        elif order.waybill_number:
            body += f"\nWaybill: {order.waybill_number}"
        send_push_async(
            order.user_id,
            title=f"Order #{order.id} update",
            body=body,
            url=f"/orders/{order.id}",
            tag=f"order-{order.id}",
        )
    except Exception:
        logger.exception("Failed to queue order status push for order_id=%s", getattr(order, 'id', None))


def push_new_message(message):
    """New community DM -- called from community/views.py send_message().
    Not rate-limited like the email nudge is: a push per message is what
    people expect from a chat, and the per-sender tag means a burst
    replaces itself on the phone instead of stacking up."""
    try:
        sender_name = message.sender.public_display_name or message.sender.username
        send_push_async(
            message.recipient_id,
            title=f"New message from {sender_name}",
            body=message.body[:140],
            url=f"/messages/{message.sender_id}",
            tag=f"dm-{message.sender_id}",
        )
    except Exception:
        logger.exception("Failed to queue DM push for message_id=%s", getattr(message, 'id', None))
