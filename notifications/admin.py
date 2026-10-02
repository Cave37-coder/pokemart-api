from django.contrib import admin, messages

from .models import PushSubscription
from .push import is_configured, send_push_to_user


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_label', 'created_at', 'last_success_at')
    list_select_related = ('user',)
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('user', 'endpoint', 'p256dh', 'auth', 'user_agent', 'created_at', 'last_success_at')
    actions = ['send_test_notification']

    def has_add_permission(self, request):
        # Rows only ever come from a customer's own browser.
        return False

    @admin.action(description="Send a test notification to the selected customers")
    def send_test_notification(self, request, queryset):
        if not is_configured():
            self.message_user(
                request,
                "VAPID keys are not set on this server -- run: python manage.py generate_vapid_keys",
                level=messages.ERROR,
            )
            return
        user_ids = set(queryset.values_list('user_id', flat=True))
        sent = 0
        for user_id in user_ids:
            sent += send_push_to_user(
                user_id,
                title='PokeBulk SA',
                body='Test notification from PokeBulk SA.',
                url='/',
                tag='test',
            )
        self.message_user(request, f"Test notification delivered to {sent} device(s) across {len(user_ids)} customer(s).")
