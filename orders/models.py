from decimal import Decimal

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


# =============================================================================
# MANUAL INVOICE — standalone admin-only invoicing tool. Deliberately has
# ZERO connection to Cart/Order/stock. EFT-only. Supports an optional
# percentage discount applied to the item subtotal (before shipping).
# =============================================================================

class ManualInvoice(models.Model):
    invoice_number = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="manual_invoices"
    )

    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)

    delivery_note = models.TextField(
        blank=True,
        help_text="Free-text delivery/collection info — address, Pudo locker, 'collection', etc."
    )
    internal_note = models.TextField(blank=True, help_text="Not shown on the invoice — your own notes only.")

    shipping_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Percentage discount applied to the item subtotal (before shipping), e.g. 10 for 10%. Leave 0 for no discount."
    )

    PAYMENT_METHOD_CHOICES = [
        ('eft', 'EFT'),
        ('cash', 'Cash'),
        ('card', 'Card'),
    ]

    # Single yes/no plus a single method -- not independent tick boxes.
    # Nothing automated reads either of these; purely Michael's own record
    # of whether and how this invoice was paid.
    payment_received = models.BooleanField(
        default=False,
        help_text="Tick once you've personally verified payment came in."
    )
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_METHOD_CHOICES, blank=True,
        help_text="Which method was used, if payment has been received."
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number or 'DRAFT'} - {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last = ManualInvoice.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.invoice_number = f"MINV-{next_num:05d}"
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0.00'))

    @property
    def discount_amount(self):
        pct = self.discount_percent or Decimal('0')
        if not pct:
            return Decimal('0.00')
        return (self.subtotal * pct / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total(self):
        return self.subtotal - self.discount_amount + (self.shipping_cost or Decimal('0.00'))

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


class ManualInvoiceItem(models.Model):
    invoice = models.ForeignKey(ManualInvoice, on_delete=models.CASCADE, related_name="items")

    # Link to a real catalog product to auto-pull its current price/details.
    # SET_NULL (never CASCADE) so deleting a product never deletes invoice
    # history — and this field is READ-ONLY as far as stock goes: nothing
    # here ever touches product.stock, on save, delete, or otherwise.
    product = models.ForeignKey(
        PokemonProduct, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Link a real catalog product to auto-pull its current price. Leave blank for off-site stock."
    )

    # Snapshot fields. Auto-filled from `product` on save if left blank —
    # or type them in by hand for stock that isn't on the site at all.
    description = models.CharField(max_length=500, blank=True, help_text="Card/item name.")
    set_name = models.CharField(max_length=255, blank=True)
    card_number = models.CharField(max_length=20, blank=True)
    variant = models.CharField(max_length=10, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Auto-filled from the linked product's current price on save. Editable at any time."
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        name = self.description or (self.product.name if self.product else "Item")
        return f"{self.quantity}x {name}"

    @property
    def line_total(self):
        return (self.unit_price or Decimal('0.00')) * self.quantity

    def save(self, *args, **kwargs):
        if self.product:
            if not self.description:
                self.description = self.product.name
            if not self.set_name and self.product.card_set:
                self.set_name = self.product.card_set.name
            if not self.card_number:
                self.card_number = self.product.card_number or ''
            if not self.variant:
                self.variant = self.product.variant_override or 'N'
            if self.unit_price is None:
                self.unit_price = self.product.price or Decimal('0.00')
        super().save(*args, **kwargs)


# =============================================================================
# BUY ORDER — the reverse of ManualInvoice: recording cards *bought from* a
# customer/seller rather than sold to one. Deliberately a separate model,
# not a repurposed ManualInvoice, since the two flows track opposite money
# movement and different fields (a seller, not a customer; a price paid,
# not charged). Like ManualInvoice, this has ZERO connection to
# PokemonProduct.stock, Cart, or Order -- buying a card here does not
# currently add it to website stock (a deliberate scope decision; can be
# revisited later).
# =============================================================================

class BuyOrder(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('eft', 'EFT'),
        ('cash', 'Cash'),
        ('card', 'Card'),
    ]

    buy_number = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="buy_orders"
    )

    seller_name = models.CharField(max_length=255)
    seller_email = models.EmailField(blank=True)
    seller_phone = models.CharField(max_length=50, blank=True)

    internal_note = models.TextField(blank=True, help_text="Your own notes only -- not shown to the seller.")

    payment_made = models.BooleanField(
        default=False,
        help_text="Tick once you've personally paid the seller."
    )
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_METHOD_CHOICES, blank=True,
        help_text="Which method was used, if payment has been made."
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.buy_number or 'DRAFT'} - {self.seller_name}"

    def save(self, *args, **kwargs):
        if not self.buy_number:
            last = BuyOrder.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.buy_number = f"BUY-{next_num:05d}"
        super().save(*args, **kwargs)

    @property
    def total(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0.00'))

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


class BuyOrderItem(models.Model):
    buy_order = models.ForeignKey(BuyOrder, on_delete=models.CASCADE, related_name="items")

    # SET_NULL, same reasoning as ManualInvoiceItem -- deleting a catalog
    # product should never delete purchase history. Never touches
    # product.stock, on save, delete, or otherwise.
    product = models.ForeignKey(
        PokemonProduct, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Link a real catalog product if it matches one. Leave blank for anything off-catalog."
    )

    description = models.CharField(max_length=500, blank=True)
    set_name = models.CharField(max_length=255, blank=True)
    card_number = models.CharField(max_length=20, blank=True)
    variant = models.CharField(max_length=10, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="What you actually paid per card/item."
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        name = self.description or (self.product.name if self.product else "Item")
        return f"{self.quantity}x {name}"

    @property
    def line_total(self):
        return (self.unit_price or Decimal('0.00')) * self.quantity

    def save(self, *args, **kwargs):
        if self.product:
            if not self.description:
                self.description = self.product.name
            if not self.set_name and self.product.card_set:
                self.set_name = self.product.card_set.name
            if not self.card_number:
                self.card_number = self.product.card_number or ''
            if not self.variant:
                self.variant = self.product.variant_override or 'N'
        super().save(*args, **kwargs)
