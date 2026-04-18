from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'trainer_level', 'is_staff']
    list_filter = ['trainer_level', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Trainer Info', {'fields': ('avatar', 'trainer_level', 'wishlist')}),
    )
