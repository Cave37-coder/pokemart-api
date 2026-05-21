from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order, OrderTracking

@receiver(post_save, sender=Order)
def create_tracking_on_status_change(sender, instance, created, **kwargs):
    if created:
        return
    last = OrderTracking.objects.filter(order=instance).order_by('-created_at').first()
    if not last or last.status != instance.status:
        OrderTracking.objects.create(
            order=instance,
            status=instance.status,
            note="",
        )
