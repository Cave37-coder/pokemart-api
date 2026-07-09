"""
JSON auth endpoints so the standalone POS frontend (hosted on
pos.pokebulk.co.za -- a different subdomain from api.pokebulk.co.za) can
authenticate using the same staff Django session that already protects
every admin view, including the existing pos/search/ and pos/save/
endpoints in ManualInvoiceAdmin. This deliberately does NOT introduce a
second, parallel auth system (e.g. tokens) -- it's the exact same
session-cookie auth the Django admin already uses, just reachable from a
different subdomain.

Four endpoints:
  GET  /api/pos-auth/csrf/    -- sets the csrftoken cookie (call first,
                                  before anything else, on every page load)
  POST /api/pos-auth/login/   -- staff-only session login
  POST /api/pos-auth/logout/  -- ends the session
  GET  /api/pos-auth/whoami/  -- checks current session state on load, so
                                  a returning tablet doesn't need to log in
                                  again every time the page opens

Why this works cross-subdomain: pos.pokebulk.co.za and api.pokebulk.co.za
share the same registrable domain (pokebulk.co.za), so the browser treats
requests between them as "same-site" for cookie purposes -- the session
and CSRF cookies are sent automatically on fetch() calls with
credentials:'include'. The one piece that needs a settings change is
CSRF_COOKIE_DOMAIN (see settings.py diff) -- without it, the POS
frontend's JS can't *read* the csrftoken cookie value to put it in the
X-CSRFToken header, because cookies are only visible to JS on the exact
host that set them unless the Domain attribute is widened.
"""
import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


@require_GET
@ensure_csrf_cookie
def pos_csrf_view(request):
    """Call this once before anything else. ensure_csrf_cookie forces
    Django to actually set the csrftoken cookie on the response -- on a
    completely fresh browser (no prior admin visit), nothing else in the
    app would trigger Django to set it, since Django only sets the cookie
    lazily when a view calls get_token()."""
    return JsonResponse({'detail': 'CSRF cookie set'})


@require_POST
def pos_login_view(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid request body'}, status=400)

    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''

    if not username or not password:
        return JsonResponse({'success': False, 'error': 'Username and password are required.'}, status=400)

    user = authenticate(request, username=username, password=password)

    if user is None:
        return JsonResponse({'success': False, 'error': 'Incorrect username or password.'}, status=401)

    if not user.is_staff:
        return JsonResponse({'success': False, 'error': 'This account does not have POS access.'}, status=403)

    login(request, user)
    # Django rotates the CSRF token on login for security -- the frontend
    # must re-read the (now different) csrftoken cookie value after this
    # call succeeds, before its next POST (e.g. saving an invoice).

    return JsonResponse({'success': True, 'username': user.username})


@require_POST
def pos_logout_view(request):
    logout(request)
    return JsonResponse({'success': True})


@require_GET
def pos_whoami_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return JsonResponse({'authenticated': True, 'username': request.user.username})
    return JsonResponse({'authenticated': False})
