from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """One row per browser / installed home-screen app that a customer has
    turned notifications on for (2026-10-02 -- "just an icon and
    notifications": the site as an installable PWA with Web Push, no app
    stores).

    A customer can have several (phone + laptop). The endpoint is the
    unique address the browser's push service (Google / Apple / Mozilla /
    Microsoft) hands out for that one device; p256dh + auth are that
    device's public encryption keys. None of the three is a secret that
    lets anyone read the customer's data -- they only allow *sending* to
    that device, and only together with our VAPID private key.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.CharField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} -- {self.device_label}"

    @property
    def device_label(self):
        ua = self.user_agent or ''
        if 'iPhone' in ua or 'iPad' in ua:
            return 'iPhone / iPad'
        if 'Android' in ua:
            return 'Android'
        if 'Windows' in ua:
            return 'Windows'
        if 'Macintosh' in ua:
            return 'Mac'
        return 'Other device'
