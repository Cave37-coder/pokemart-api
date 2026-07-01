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
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
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
                f"This link expires in a few hours and can only be used once. "
                f"If you didn't request this, you can safely ignore this email "
                f"-- your password will not be changed.\n\n"
                f"-- PokeBulk SA"
            )
            html_body = f'''<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#222;padding:20px">
<h2 style="color:#ff6b35">Reset your password</h2>
<p>Hi {user.first_name or user.username},</p>
<p>We received a request to reset your PokeBulk SA password. Click the button below to choose a new one:</p>
<p><a href="{reset_url}" style="background:#ff6b35;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block">Reset Password</a></p>
<p style="font-size:12px;color:#888">This link expires in a few hours and can only be used once. If you didn't request this, you can safely ignore this email -- your password will not be changed.</p>
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
            except Exception:
                # Don't leak SMTP failures to the client -- still return the
                # generic success message either way, per the anti-enumeration
                # design above. If emails are silently failing, that's a
                # backend monitoring concern, not something to surface here.
                pass

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

        user.set_password(new_password)
        user.save(update_fields=['password'])
        return Response({'detail': 'Password has been reset successfully.'})
