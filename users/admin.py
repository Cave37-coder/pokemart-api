from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'trainer_level', 'is_staff', 'community_profile_public', 'messaging_enabled']
    list_filter = ['trainer_level', 'is_staff', 'community_profile_public', 'messaging_enabled', 'checklist_public']
    fieldsets = UserAdmin.fieldsets + (
        ('Trainer Info', {'fields': ('avatar', 'trainer_level', 'wishlist')}),
        ('Community', {'fields': (
            'public_display_name', 'community_bio',
            'checklist_public', 'community_profile_public', 'messaging_enabled',
        )}),
    )
