from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = 'orders'

    def ready(self):
        # Michael, 2026-08-11: "are emails been sent, when i am change the
        # status of orders???" -- found live: orders/signals.py's
        # create_tracking_on_status_change / _send_status_update_email were
        # fully written (courier/waybill info, BCC to admin@, the lot) but
        # this file was NEVER imported anywhere, so Django never registered
        # the @receiver and the post_save signal never fired -- every order
        # status change silently sent nothing, since the checkout-time
        # confirmation email (CheckoutView, unaffected by this) is a
        # different, inline code path. This import is what actually
        # activates the signal; it must live in ready(), not at module
        # level in models.py, per Django's own app-loading docs (importing
        # signal handlers before the app registry is fully populated can
        # cause obscure errors).
        import orders.signals  # noqa: F401

