import logging

from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order, OrderTracking

logger = logging.getLogger(__name__)


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
        _send_status_update_email(instance)


def _send_status_update_email(order):
    """
    Automated, simple status-update email to the customer whenever an
    order's status changes -- distinct from the full invoice email sent
    once at order placement (CheckoutView.post()). No BCC to enquiries@ on
    these, per instruction: only the initial order-confirmation email gets
    a copy sent there.

    Deliberately fires from the model-save signal, not from
    OrderStatusUpdateView or the Django admin directly -- both of those
    paths end up calling Order.save(), so hooking the signal covers every
    status-change route (API and admin) with one implementation, matching
    how OrderTracking creation itself already works here.

    Wrapped in try/except: a failed email must never block a staff member
    from saving a status change in the admin, or break the status-update
    API endpoint. Failures are logged instead of raised.
    """
    try:
        customer_email = order.user.email
        if not customer_email:
            logger.warning(
                "Order #%s status changed to %s but user_id=%s has no email on file -- update not sent.",
                order.id, order.status, order.user_id,
            )
            return

        customer_name = f"{order.user.first_name}".strip() or order.user.username
        status_label = order.get_status_display()

        subject = f'Your PokeBulk SA order #{order.id} update: {status_label}'
        text_body = (
            f"Hi {customer_name},\n\n"
            f"Your PokeBulk SA order #{order.id} has been updated:\n\n"
            f"    Status: {status_label}\n\n"
            f"You can view your full order details anytime by signing in at "
            f"https://pokebulk.co.za/orders/{order.id}\n\n"
            f"-- PokeBulk SA"
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            to=[customer_email],
        )
        email.send(fail_silently=False)
        logger.info(
            "Order status-update email sent for order_id=%s status=%s to=%s",
            order.id, order.status, customer_email,
        )
    except Exception:
        logger.exception(
            "Failed to send order status-update email for order_id=%s status=%s",
            order.id, order.status,
        )
