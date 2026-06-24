from django.db import models
from django.conf import settings
from products.models import PokemonProduct


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.user.username})"

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(PokemonProduct, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def subtotal(self):
        return (self.product.price or 0) * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ("awaiting_payment", "Awaiting Payment"),
        ("pending",         "Order Received"),
        ("pending_eft",     "Awaiting EFT Payment"),
        ("printed",         "Order Printed"),
        ("packed",          "Order Packed"),
        ("booked",          "Courier Booking"),
        ("ready",           "Ready for Collection"),
        ("collected",       "Courier Collected"),
        ("invoiced",        "Final Invoice"),
        ("cancelled",       "Cancelled"),
    ]

    DELIVERY_CHOICES = [
        ("courier",    "Courier"),
        ("collection", "Collection"),
    ]

    PAYMENT_CHOICES = [
        ("payfast",    "PayFast"),
        ("eft",        "EFT / Bank Transfer"),
        ("coc",        "Cash on Collection"),
    ]

    # Manual admin-only payment verification — purely a record for Michael's own
    # bookkeeping. Nothing in the system reads, writes, or automates against
    # these fields; they exist so he can mark "I personally checked this got paid".
    PAYMENT_CONFIRMED_METHOD_CHOICES = [
        ("cash",    "Cash"),
        ("eft",     "EFT"),
        ("payfast", "PayFast"),
    ]

    SHIPPING_CHOICES = [
        ("collection",  "Cash on Collection"),
        ("pudo_locker", "Pudo Locker-to-Locker"),
        ("pudo_kiosk",  "Pudo Locker-to-Kiosk"),
        ("pudo_medium", "Pudo Medium/Tins Kiosk"),
        ("pudo_door",   "Pudo Locker-to-Door"),
        ("pudo_door",   "Pudo Door-to-Door"),
        ("postnet",     "Postnet-to-Postnet"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_intent = models.CharField(max_length=200, blank=True)

    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="payfast", blank=True)
    eft_confirmed = models.BooleanField(default=False, help_text="Tick when EFT payment received in bank account")

    # Manual admin payment verification (separate from the automated payment_method
    # above — this is Michael's own personal check, not tied to any system logic)
    payment_confirmed = models.BooleanField(
        default=False,
        help_text="Manual check only — tick once you've personally verified this order was paid. Nothing automated reads this."
    )
    payment_confirmed_method = models.CharField(
        max_length=20, choices=PAYMENT_CONFIRMED_METHOD_CHOICES, blank=True,
        help_text="Your own record of how payment actually came in."
    )

    # Shipping
    shipping_method = models.CharField(max_length=20, choices=SHIPPING_CHOICES, default="pudo_locker", blank=True)
    shipping_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Delivery
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default="courier", blank=True)
    delivery_address_line1 = models.CharField(max_length=255, blank=True)
    delivery_address_line2 = models.CharField(max_length=255, blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_province = models.CharField(max_length=100, blank=True)
    delivery_postal_code = models.CharField(max_length=20, blank=True)
    pudo_locker_name = models.CharField(max_length=255, blank=True)
    pudo_locker_address = models.CharField(max_length=255, blank=True)

    # Courier
    waybill_number = models.CharField(max_length=100, blank=True)
    courier_name = models.CharField(max_length=100, blank=True)
    courier_tracking_url = models.URLField(blank=True)

    # Notes
    customer_note = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        """
        Automatic stock restoration on cancellation, and re-decrement if an
        order is un-cancelled. Fires no matter which path triggered the save
        — Django admin or the API's OrderStatusUpdateView — since both end
        up calling this same save() method. Stock decrement on order
        creation is handled separately in CheckoutView (this only reacts to
        a STATUS CHANGE on an existing order, never on initial creation).
        """
        restore_stock = False
        redecrement_stock = False

        if self.pk:
            old_status = Order.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status is not None and old_status != self.status:
                if self.status == 'cancelled' and old_status != 'cancelled':
                    restore_stock = True
                elif old_status == 'cancelled' and self.status != 'cancelled':
                    redecrement_stock = True

        super().save(*args, **kwargs)

        if restore_stock:
            self._adjust_stock(direction=1)
        elif redecrement_stock:
            self._adjust_stock(direction=-1)

    def _adjust_stock(self, direction):
        """direction=+1 restores stock (order cancelled), direction=-1
        re-reserves it (order un-cancelled back to an active status)."""
        for item in self.items.select_related('product').all():
            if item.product is None:
                continue
            item.product.stock = max(0, item.product.stock + (direction * item.quantity))
            item.product.save(update_fields=['stock'])


class OrderTracking(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tracking")
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    note = models.TextField(blank=True)
    waybill_number = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tracking_updates"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Order #{self.order.id} -> {self.get_status_display()} @ {self.created_at:%Y-%m-%d %H:%M}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(PokemonProduct, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=500, blank=True)  # snapshot at purchase
    product_sku = models.CharField(max_length=200, blank=True)   # snapshot at purchase
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        name = self.product_name or (self.product.name if self.product else "Deleted product")
        return f"{self.quantity}x {name}"

    @property
    def subtotal(self):
        return (self.price_at_purchase or 0) * self.quantity
