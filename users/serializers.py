from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    # Required for registration only -- the User model itself keeps these
    # as blank=True (changing that would need a data migration and would
    # immediately invalidate every existing account that doesn't yet have
    # these filled in, which is exactly the population the separate
    # "complete your profile" popup is meant to handle, not break).
    first_name = serializers.CharField(required=True, allow_blank=False, max_length=150)
    last_name = serializers.CharField(required=True, allow_blank=False, max_length=150)
    email = serializers.EmailField(required=True, allow_blank=False)
    phone_number = serializers.CharField(required=True, allow_blank=False, max_length=20)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'trainer_level', 'first_name', 'last_name', 'phone_number', 'address_line1', 'address_line2', 'address_city', 'address_province', 'address_postal_code', 'pudo_locker_name', 'pudo_locker_address']
        read_only_fields = ['id', 'trainer_level']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data['phone_number'],
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(**data)
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        if not user.is_active:
            raise serializers.ValidationError('Account is disabled')
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'trainer_level', 'avatar', 'created_at', 'is_staff', 'is_superuser']
        read_only_fields = ['id', 'created_at']


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
