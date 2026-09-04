"""
Michael, 2026-09-04: "put the full list there in chronological order of
when they last were on the site" -- the site had no "last seen" signal at
all before this (Django's own User.last_login is never touched: LoginView
issues JWTs directly rather than going through Django's own login(), which
is the only thing that updates it). This middleware fills that gap by
reading the JWT straight off the Authorization header on every request (no
need to fully re-run DRF's own authentication) and stamping User.last_seen
-- throttled to at most once every 5 minutes per user so a customer
actively browsing doesn't trigger a DB write on every single API call.

Deliberately silent on any failure (missing/expired/malformed token, no
header at all, anything) -- this must never be the thing that breaks a
request; if it can't confidently identify a user it just does nothing.
"""
from datetime import timedelta

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q

LAST_SEEN_THROTTLE = timedelta(minutes=5)


class UpdateLastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._touch_last_seen(request)
        return self.get_response(request)

    def _touch_last_seen(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(auth_header.split(' ', 1)[1])
            user_id = token['user_id']
        except Exception:
            return

        try:
            now = timezone.now()
            cutoff = now - LAST_SEEN_THROTTLE
            User = get_user_model()
            User.objects.filter(pk=user_id).filter(
                Q(last_seen__isnull=True) | Q(last_seen__lt=cutoff)
            ).update(last_seen=now)
        except Exception:
            # Never let last-seen tracking break a real request.
            pass
