import logging

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
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
        # _tracking_note/_tracking_waybill/_tracking_created_by are plain
        # (non-model, never-saved) attributes OrderStatusUpdateView stashes
        # onto the instance right before calling .save(), so this one
        # signal handler -- the single place any status change creates a
        # tracking row or sends the update email, from any code path --
        # can still record who made the change and any note/waybill they
        # attached, not just the bare status. Falls back to the instance's
        # real waybill_number when nothing was stashed (e.g. a status
        # change made directly through the Django admin form, which sets
        # waybill_number on the instance itself before save() rather than
        # stashing a separate attribute).
        OrderTracking.objects.create(
            order=instance,
            status=instance.status,
            note=getattr(instance, '_tracking_note', '') or '',
            waybill_number=getattr(instance, '_tracking_waybill', '') or instance.waybill_number or '',
            created_by=getattr(instance, '_tracking_created_by', None),
        )
        # BUG FIX 2026-08-12 (Michael: "everytime i retry, it sends email
        # again!" alongside a "Failed to save" error on the staff dashboard):
        # OrderStatusUpdateView.patch() wraps its whole body in
        # @transaction.atomic, and this signal fires synchronously INSIDE
        # that transaction (post_save runs before order.save() even
        # returns). If anything after order.save() then fails -- e.g. a
        # slow response on a huge order timing out before the client sees
        # it -- the whole transaction rolls back: the status change and the
        # OrderTracking row both get undone, but the email had ALREADY gone
        # out over SMTP and can't be un-sent. From the DB's point of view
        # nothing happened, so a retry looks like a brand new status change
        # every time -- another tracking row attempt, another email, on and
        # on for every retry, while the customer just keeps getting spammed
        # and Michael never sees a save actually succeed. Same root cause
        # CheckoutView and the Manual Invoice POS save already had to be
        # fixed for once before ("email sent but nothing in the DB"). Fix is
        # the same: only actually send once the transaction has truly
        # committed -- if it rolls back, this callback is simply discarded
        # and no email goes out at all.
        transaction.on_commit(lambda: _send_status_update_email(instance))


def _send_status_update_email(order):
    """
    Automated, simple status-update email to the customer whenever an
    order's status changes -- distinct from the full invoice email sent
    once at order placement (CheckoutView.post()). BCC's admin@pokebulk.co.za
    (Michael, 2026-08-02) so staff see every status-change email as it goes
    out, same as enquiries@ gets on the initial order-confirmation email.

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
        )

        # Michael, 2026-08-12: include whatever waybill/tracking info is on
        # file on EVERY status-update email once it's been added to the
        # order, not just on the 'booked'/'collected' statuses -- so the
        # tracking number keeps showing up (e.g. on the later "Complete"
        # email) instead of only appearing once and then disappearing.
        courier_lines = []
        if order.courier_name:
            courier_lines.append(f"    Courier: {order.courier_name}")
        if order.waybill_number:
            courier_lines.append(f"    Waybill / Tracking Number: {order.waybill_number}")
        if order.courier_tracking_url:
            courier_lines.append(f"    Track your parcel: {order.courier_tracking_url}")
        if courier_lines:
            text_body += "\n".join(courier_lines) + "\n\n"

        text_body += (
            f"You can view your full order details anytime by signing in at "
            f"https://pokebulk.co.za/orders/{order.id}\n\n"
            f"-- PokeBulk SA"
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            to=[customer_email],
            bcc=['admin@pokebulk.co.za'],
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
