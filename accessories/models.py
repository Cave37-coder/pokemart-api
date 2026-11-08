# pokemart-api: accessories/models.py
#
# Non-card catalog: sleeves, deck boxes, playmats, storage, etc. Deliberately
# its own lean model rather than reusing PokemonProduct (2026-08-07, Michael
# confirmed "New separate model" over extending the card model) -- an
# accessory has none of PokemonProduct's 50+ card-specific fields (pokedex
# number, HP, attacks, card_set, variant...), so bolting it on there would
# mean either a wall of nullable card fields on every sleeve/deck box, or a
# constant risk of card-only logic (checklist tiers, Pokedex catching,
# variant scoring) accidentally treating an accessory as a card.
#
# Data source: TCGCSV's game-agnostic supply categories (same public API
# that already feeds the card catalog -- see the ACCESSORY_CATEGORY_IDS
# import command). Michael confirmed there's no separate live "PoBuSA" or
# POS API to pull from yet -- that project is still local/undeployed -- so
# this goes straight to TCGCSV, matching the pattern already prototyped in
# pull_pokemon_sleeves.py from an earlier session.

from django.conf import settings
from django.db import models


class Accessory(models.Model):
    CATEGORY_CHOICES = [
        ("sleeves", "Card Sleeves"),
        ("deck_boxes", "Deck Boxes"),
        ("storage_tins", "Card Storage Tins"),
        ("life_counters", "Life Counters"),
        ("playmats", "Playmats"),
        ("protective_pages", "Protective Pages"),
        ("storage_albums", "Storage Albums"),
        ("collectible_storage", "Collectible Storage"),
        ("supply_bundles", "Supply Bundles"),
        ("supplies", "Supplies"),
        # 2026-10-26: sealed product (ETBs, boosters, collection boxes) bought
        # in through the buying invoice -- Michael: "Also need to be able to
        # [buy in] other products too". Same lean model, no card fields.
        ("sealed", "Sealed Product"),
        ("other", "Other"),
    ]

    sku = models.CharField(max_length=20, unique=True, blank=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="other")
    manufacturer = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    image_url = models.URLField(max_length=500, blank=True)
    # Where image_url was originally taken from (TCGplayer CDN etc.) before it
    # was re-hosted on R2 -- kept so a re-host can be re-run, never shown to
    # customers. image_url itself must always end up on images.pokebulk.co.za
    # (CLAUDE.md "Image hosting -- always R2").
    image_source_url = models.URLField(max_length=500, blank=True)

    # Manufacturer barcode (UPC/EAN), for the future in-store POS -- Michael,
    # 2026-10-26: "not needed for site, but later ... a POS, to link store and
    # website as one". Optional; unique when filled (null, not "", when empty
    # so the unique constraint ignores blanks).
    barcode = models.CharField(max_length=50, blank=True, null=True, unique=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    # Drives "customers only see what is in Stock" (Michael, 2026-08-07) --
    # unlike PokemonProduct, where an out-of-stock card still shows
    # (greyed-out) so customers can see it exists, an out-of-stock accessory
    # is hidden from the public API entirely. See accessories/views.py.
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # True once a price was set by hand (admin) or by a completed buying
    # invoice's sell price -- sync_accessories then leaves price alone, same
    # idea as PokemonProduct.price_locked.
    price_locked = models.BooleanField(
        default=False,
        help_text="Keep this price -- the TCGCSV sync will not overwrite it.",
    )

    # Import bookkeeping -- lets a re-sync update an existing row (price/
    # stock/name refresh) instead of creating a duplicate every run, and
    # shows Michael exactly where a row came from.
    tcgcsv_product_id = models.IntegerField(null=True, blank=True, unique=True)
    tcgcsv_category_id = models.IntegerField(null=True, blank=True)
    tcgplayer_url = models.URLField(max_length=500, blank=True)
    source_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # The product row My Pile / checkout sell this accessory through
    # (2026-11-08) -- see accessories/cart_link.py. Once linked, THAT row's
    # stock is the real stock; Accessory.stock is kept as a copy.
    cart_product = models.OneToOneField(
        "products.PokemonProduct", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="accessory_listing", editable=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Accessories"

    def __str__(self):
        return f"{self.sku} - {self.name}" if self.sku else self.name

    @property
    def in_stock(self):
        return self.stock > 0

    def generate_sku(self):
        last = Accessory.objects.order_by("id").last()
        next_num = (last.id + 1) if last else 1
        return f"ACC-{str(next_num).zfill(4)}"

    def save(self, *args, **kwargs):
        if not self.barcode:
            self.barcode = None  # blank -> NULL so unique=True ignores it
        if not self.sku:
            self.sku = self.generate_sku()
        old_stock = None
        if self.pk:
            old_stock = Accessory.objects.filter(pk=self.pk).values_list("stock", flat=True).first()
        super().save(*args, **kwargs)
        # Keep the Pile's product row in step (accessories/cart_link.py). A
        # changed stock here is a staff edit -> it becomes the live stock.
        from .cart_link import push_to_product
        push_to_product(self, set_stock=(old_stock is not None and old_stock != self.stock))


class SealedCollectionItem(models.Model):
    """A sealed product (ETB, booster box, tin...) a customer owns -- their "Sealed Collection".
    2026-11-04, Michael: tracked on its own, separate from card collections. The product is a PokemonProduct row
    with supertype "Sealed" (the same rows the shop sells). Value = our current price."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sealed_items")
    product = models.ForeignKey("products.PokemonProduct", on_delete=models.CASCADE, related_name="sealed_collection_items")
    quantity = models.PositiveIntegerField(default=1)
    value_when_added = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_sealed_collection_item")]
        ordering = ["-added_at"]
