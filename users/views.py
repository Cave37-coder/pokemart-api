import logging
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMultiAlternatives
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def check_rate_limit(key, limit, window_seconds):
    """
    Returns (allowed: bool, attempts_remaining: int).
    Uses Django's cache to track attempts per key within a rolling window.
    key    -- unique string identifying the rate-limit bucket (e.g. "login:1.2.3.4")
    limit  -- max attempts allowed within the window
    window -- seconds before the count resets
    """
    cache_key = f"rl:{key}"
    count = cache.get(cache_key, 0)
    if count >= limit:
        return False, 0
    cache.set(cache_key, count + 1, timeout=window_seconds)
    return True, limit - count - 1


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ip = get_client_ip(request)
        allowed, remaining = check_rate_limit(f"login:{ip}", limit=10, window_seconds=600)
        if not allowed:
            return Response(
                {'error': 'Too many login attempts. Please try again in 10 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        return Response({'detail': 'Logged out successfully'})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
from django.contrib.auth import get_user_model
User = get_user_model()

# Fields required for a "complete" profile, per the 2026-06-21 decision to
# require First Name / Last Name / Email / Phone Number for communication
# purposes. Kept as a single list so the frontend "complete your profile"
# popup (and any future check) only needs to read profile_complete below
# rather than re-implementing this logic -- if the required set ever
# changes, it only needs to change here.
REQUIRED_PROFILE_FIELDS = ["first_name", "last_name", "email", "phone_number"]


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        profile_complete = all(getattr(u, field, "") for field in REQUIRED_PROFILE_FIELDS)
        return Response({
            "id": u.id, "username": u.username, "email": u.email,
            "first_name": u.first_name, "last_name": u.last_name,
            "phone_number": u.phone_number, "trainer_level": u.trainer_level,
            "delivery_preference": u.delivery_preference,
            "address_line1": u.address_line1, "address_line2": u.address_line2,
            "address_city": u.address_city, "address_province": u.address_province,
            "address_postal_code": u.address_postal_code,
            "pudo_locker_name": u.pudo_locker_name,
            "pudo_locker_address": u.pudo_locker_address,
            "pudo_locker_code": u.pudo_locker_code,
            "public_display_name": u.public_display_name,
            "checklist_public": u.checklist_public,
            "community_profile_public": u.community_profile_public,
            "community_bio": u.community_bio,
            "messaging_enabled": u.messaging_enabled,
            "profile_complete": profile_complete,
        })

    def patch(self, request):
        u = request.user
        allowed = [
            "first_name", "last_name", "email", "phone_number",
            "delivery_preference",
            "address_line1", "address_line2", "address_city",
            "address_province", "address_postal_code",
            "pudo_locker_name", "pudo_locker_address", "pudo_locker_code",
            "public_display_name", "checklist_public",
            "community_profile_public", "community_bio", "messaging_enabled",
        ]
        for field in allowed:
            if field in request.data:
                setattr(u, field, request.data[field])
        u.save()
        return self.get(request)


class PasswordResetRequestView(APIView):
    """
    Takes an email, and if a matching active user exists, emails them a
    reset link. Always returns a generic success message regardless of
    whether the email matched a real account -- this is deliberate, to
    avoid leaking which emails are registered (a common account-enumeration
    vulnerability). The actual email is only sent on a real match.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ip = get_client_ip(request)
        allowed, _ = check_rate_limit(f"pwreset:{ip}", limit=3, window_seconds=900)
        if not allowed:
            # This used to return silently here with no log line at all --
            # meaning a rate-limited attempt looked identical to a genuine
            # successful send from the outside (same 200, same message),
            # but nothing was ever actually attempted or recorded. Logging
            # it now means "no email arrived" can be diagnosed in seconds
            # instead of requiring a full investigation each time.
            logger.warning(
                "Password reset request rate-limited for ip=%s -- no email attempted",
                ip,
            )
            return Response(
                {'detail': 'If an account exists with that email, a reset link has been sent.'}
            )
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        User = get_user_model()
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            site_url = getattr(settings, 'SITE_URL', 'https://pokebulk.co.za')
            reset_url = f'{site_url}/auth/reset-password/{uid}/{token}'

            text_body = (
                f"Hi {user.first_name or user.username},\n\n"
                f"We received a request to reset your PokeBulk SA password. "
                f"Click the link below to choose a new one:\n\n{reset_url}\n\n"
                f"This link is valid for up to 3 days and can only be used once. "
                f"Important: don't log in to your account before using this link -- "
                f"logging in (even a failed attempt on the old password) will "
                f"invalidate it, and you'll need to request a new one.\n\n"
                f"If you didn't request this, you can safely ignore this email "
                f"-- your password will not be changed.\n\n"
                f"-- PokeBulk SA"
            )
            html_body = f'''<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#222;padding:20px">
<h2 style="color:#ff6b35">Reset your password</h2>
<p>Hi {user.first_name or user.username},</p>
<p>We received a request to reset your PokeBulk SA password. Click the button below to choose a new one:</p>
<p><a href="{reset_url}" style="background:#ff6b35;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block">Reset Password</a></p>
<p style="font-size:12px;color:#888">This link is valid for up to 3 days and can only be used once. <strong>Don't log in to your account before using this link</strong> -- doing so will invalidate it, and you'll need to request a new one.</p>
<p style="font-size:12px;color:#888">If you didn't request this, you can safely ignore this email -- your password will not be changed.</p>
<p style="font-size:12px;color:#888">-- PokeBulk SA</p>
</body></html>'''

            try:
                email_msg = EmailMultiAlternatives(
                    subject='Reset your PokeBulk SA password',
                    body=text_body,
                    to=[user.email],
                )
                email_msg.attach_alternative(html_body, 'text/html')
                email_msg.send(fail_silently=False)
                logger.info(
                    "Password reset email sent successfully for user_id=%s email=%s",
                    user.pk, user.email,
                )
            except Exception:
                # Still return the generic success message either way, per the
                # anti-enumeration design above -- but log the real failure so
                # it's visible in Railway logs instead of vanishing silently.
                logger.exception(
                    "Password reset email failed to send for user_id=%s email=%s",
                    user.pk, user.email,
                )
        else:
            logger.info(
                "Password reset requested for email=%s -- no matching active user found",
                email,
            )

        return Response({
            'detail': 'If an account exists with that email, a reset link has been sent.'
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        User = get_user_model()
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        # Michael, 2026-08-08: found live via diagnose_duplicate_emails.py --
        # 15 email addresses (30 accounts) in production are shared by more
        # than one registered username (duplicate signups). The reset link
        # is only ever minted for ONE specific account (the uid baked into
        # it), but the customer has no way of knowing -- or controlling --
        # which of their duplicate usernames PasswordResetRequestView
        # happened to pick when it looked up that email. Result: "reset
        # says success, but login still fails" whenever they normally log
        # in under the OTHER username -- reproduced exactly on Michael's
        # own Ty/CaVe37 accounts. Setting the new password on every active
        # account sharing this email (not just the one in the link) makes
        # the reset actually usable regardless of which duplicate username
        # the customer logs in with, without deleting or merging anything.
        if user.email:
            siblings = User.objects.filter(email__iexact=user.email, is_active=True).exclude(pk=user.pk)
            for sibling in siblings:
                sibling.set_password(new_password)
                sibling.save(update_fields=['password'])
                logger.info(
                    "Password reset also propagated to duplicate-email sibling "
                    "user_id=%s username=%s (reset link was for user_id=%s username=%s)",
                    sibling.pk, sibling.username, user.pk, user.username,
                )

        user.set_password(new_password)
        user.save(update_fields=['password'])
        return Response({'detail': 'Password has been reset successfully.'})


class ChangePasswordView(APIView):
    """
    Michael, 2026-08-07: "add to Profile, that you can change Password" --
    for a customer who's already logged in, unlike PasswordResetRequest/
    ConfirmView above which exist specifically for someone who is NOT
    logged in and needs an emailed token instead. Requires the current
    password so a stolen/left-open session alone isn't enough to lock the
    real owner out.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = get_client_ip(request)
        allowed, _ = check_rate_limit(f"changepw:{request.user.pk}:{ip}", limit=5, window_seconds=900)
        if not allowed:
            return Response(
                {'error': 'Too many attempts. Please wait a few minutes and try again.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        if not request.user.check_password(current_password):
            return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save(update_fields=['password'])
        logger.info("Password changed via profile for user_id=%s", request.user.pk)
        return Response({'detail': 'Password updated successfully.'})


# ── Wishlist (2026-08-07) ────────────────────────────────────────────────
# The `wishlist` M2M field on User has existed since 0001_initial but never
# had an API -- these two views are the first thing that actually lets a
# customer manage it. Same toggle pattern as products.views.pokedex_toggle
# for consistency (one endpoint, existence of the relation IS the state).
from rest_framework.decorators import api_view, permission_classes
from products.models import PokemonProduct
from products.serializers import PokemonProductSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wishlist_list(request):
    """This customer's own wishlist, full card data (same shape the rest of
    the site already uses for CardTile). GET /api/auth/wishlist/"""
    products = request.user.wishlist.select_related('card_set', 'card_set__era').all()
    return Response({
        'product_ids': list(products.values_list('id', flat=True)),
        'products': PokemonProductSerializer(products, many=True, context={'request': request}).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wishlist_toggle(request):
    """Adds/removes one card from this customer's wishlist.
    POST /api/auth/wishlist/toggle/  body: {"product_id": 123}"""
    product_id = request.data.get('product_id')
    if not product_id:
        return Response({'error': 'product_id is required'}, status=400)
    try:
        product = PokemonProduct.objects.get(pk=product_id)
    except PokemonProduct.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)

    if request.user.wishlist.filter(pk=product.pk).exists():
        request.user.wishlist.remove(product)
        return Response({'on_wishlist': False})
    request.user.wishlist.add(product)
    return Response({'on_wishlist': True})


# ── Staff: customer checklist lookup (2026-08-12) ───────────────────────────
# Michael: "I also want access to customers checklists, so that i can check
# what they need!" -- distinct from community/views.py's public_profile,
# which only exposes full_checklist to FRIENDS or when checklist_public is
# on. Staff need to look up ANY customer regardless of their privacy opt-ins
# (same reasoning Django admin already has full visibility), so this is a
# separate IsAdminUser-only endpoint rather than loosening the customer-facing
# privacy gates. Feeds the /staff/checklists page's customer search box.
from rest_framework.permissions import IsAdminUser
from django.contrib.auth import get_user_model
from django.db.models import Count, Q


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_customer_search(request):
    """GET /api/auth/admin/customers/?search=theuns
    With no search, returns customers who actually have checklist activity,
    busiest collector first -- more useful for staff browsing than an
    alphabetical dump of every account ever registered."""
    User = get_user_model()
    search = request.GET.get('search', '').strip()
    qs = User.objects.annotate(checklist_count=Count('checklist_entries', distinct=True))
    if search:
        qs = qs.filter(
            Q(username__icontains=search) | Q(email__icontains=search)
            | Q(first_name__icontains=search) | Q(last_name__icontains=search)
        )
    else:
        qs = qs.filter(checklist_count__gt=0)
    qs = qs.order_by('-checklist_count', 'username')[:50]
    return Response([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'first_name': u.first_name,
        'last_name': u.last_name,
        'checklist_count': u.checklist_count,
    } for u in qs])
