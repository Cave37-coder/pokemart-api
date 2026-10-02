from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from users.views import check_rate_limit
from .models import PushSubscription
from .push import is_allowed_endpoint, is_configured, send_push_to_user

# A customer realistically has a phone, maybe a tablet and a laptop.
MAX_SUBSCRIPTIONS_PER_USER = 10


@api_view(['GET'])
@permission_classes([AllowAny])
def public_key(request):
    """GET /api/push/public-key/ -- the VAPID *public* key the browser needs
    in order to subscribe. Public by design (it is the half that is meant
    to be handed out), served from here so it only has to be configured in
    one place (Railway) instead of on Vercel as well."""
    if not is_configured():
        return Response({'error': 'Push notifications are not set up yet.'}, status=503)
    return Response({'public_key': settings.VAPID_PUBLIC_KEY})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe(request):
    """POST /api/push/subscribe/
    body: {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}
    (exactly what the browser's PushSubscription.toJSON() produces).

    Keyed on endpoint, so calling it again from the same device just
    refreshes the row -- and if a different customer signs in on that same
    phone, the device moves over to them instead of the previous customer's
    order updates landing on it."""
    endpoint = (request.data.get('endpoint') or '').strip()
    keys = request.data.get('keys') or {}
    p256dh = (keys.get('p256dh') or '').strip() if isinstance(keys, dict) else ''
    auth = (keys.get('auth') or '').strip() if isinstance(keys, dict) else ''

    if not endpoint or not p256dh or not auth:
        return Response({'error': 'endpoint and keys are required'}, status=400)
    if len(endpoint) > 1000 or len(p256dh) > 255 or len(auth) > 255:
        return Response({'error': 'Invalid subscription'}, status=400)
    if not is_allowed_endpoint(endpoint):
        return Response({'error': 'Unsupported push service'}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:300],
        },
    )

    stale = list(
        PushSubscription.objects.filter(user=request.user)
        .order_by('-created_at')
        .values_list('pk', flat=True)[MAX_SUBSCRIPTIONS_PER_USER:]
    )
    if stale:
        PushSubscription.objects.filter(pk__in=stale).delete()

    return Response({'ok': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unsubscribe(request):
    """POST /api/push/unsubscribe/  body: {"endpoint": "..."}"""
    endpoint = (request.data.get('endpoint') or '').strip()
    if not endpoint:
        return Response({'error': 'endpoint is required'}, status=400)
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return Response({'ok': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test(request):
    """POST /api/push/test/ -- sends a test notification to the logged-in
    customer's own devices only, so they can confirm it works."""
    if not is_configured():
        return Response({'error': 'Push notifications are not set up yet.'}, status=503)
    allowed, _ = check_rate_limit(f"push_test:{request.user.id}", limit=5, window_seconds=600)
    if not allowed:
        return Response({'error': 'Too many test notifications. Try again in a few minutes.'}, status=429)
    sent = send_push_to_user(
        request.user.id,
        title='PokeBulk SA',
        body="Notifications are on. We'll let you know when your orders move.",
        url='/orders',
        tag='test',
    )
    return Response({'sent': sent})
