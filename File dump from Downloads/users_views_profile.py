# Add these to users/views.py — profile get/update endpoint

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileView(APIView):
    """
    GET  /api/auth/profile/   — get current user profile
    PATCH /api/auth/profile/  — update profile fields
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            'id':                   u.id,
            'username':             u.username,
            'email':                u.email,
            'first_name':           u.first_name,
            'last_name':            u.last_name,
            'phone_number':         u.phone_number,
            'trainer_level':        u.trainer_level,
            'delivery_preference':  u.delivery_preference,
            # Address
            'address_line1':        u.address_line1,
            'address_line2':        u.address_line2,
            'address_city':         u.address_city,
            'address_province':     u.address_province,
            'address_postal_code':  u.address_postal_code,
            # Pudo
            'pudo_locker_name':     u.pudo_locker_name,
            'pudo_locker_address':  u.pudo_locker_address,
            'pudo_locker_code':     u.pudo_locker_code,
        })

    def patch(self, request):
        u = request.user
        allowed = [
            'first_name', 'last_name', 'email', 'phone_number',
            'delivery_preference',
            'address_line1', 'address_line2', 'address_city',
            'address_province', 'address_postal_code',
            'pudo_locker_name', 'pudo_locker_address', 'pudo_locker_code',
        ]
        for field in allowed:
            if field in request.data:
                setattr(u, field, request.data[field])
        u.save()
        return self.get(request)
