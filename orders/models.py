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
