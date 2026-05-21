from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer


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

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
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
