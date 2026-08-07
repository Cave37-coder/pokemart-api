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

    # Michael, 2026-08-08: found live -- 15 email addresses (30 accounts)
    # already exist as duplicate signups, and it's the root cause of the
    # "reset succeeds, login still fails" reports (a reset link is only
    # ever minted for ONE of the duplicate accounts). Fixed the reset flow
    # itself to update every account sharing an email, but that doesn't
    # stop the underlying duplicate from being created in the first place --
    # this closes that off going forward. Existing duplicates are untouched
    # here; Michael can decide separately how those should be merged/cleaned.
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account already exists with this email. Try signing in, "
                "or use 'Forgot password' if you don't remember your username."
            )
        return value

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


# Michael, 2026-08-07: "add to Profile that you can change password" --
# separate from the logged-out PasswordReset* flow above (which needs an
# email link because the customer can't authenticate at all). This is for
# a customer who IS logged in and just wants to change it from /profile,
# so it takes their current password instead of an emailed token.
class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
