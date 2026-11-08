"""
Accessories in My Pile (2026-11-08) -- Michael: "I can't select any
accessories, so it won't go into My Pile to be purchased!!"

The Pile, checkout, orders, invoices and stock restore all work on
PokemonProduct rows only. Sealed product already moved onto that table for
exactly this reason (accessories migration 0005). Accessories keep their own
lean model (admin, TCGCSV sync, buying invoices), and each one is now linked
to ONE product row (supertype "Accessory") that the Pile sells.

STOCK -- one source of truth: once linked, the product row's stock is the
real stock (orders/cancellations/manual invoices move it, many of them with
queryset .update(), which no signal sees). Accessory.stock is a copy:
  * refresh_accessory_stock() copies product stock back onto every linked
    accessory -- run before the public list and before staff see the admin,
    so a number staff edit is always the current one;
  * push_to_product() copies price/name/image/active onto the product and,
    when staff changed the stock (admin edit, buying invoice), writes that
    stock onto the product too.
Product rows with supertype "Accessory" are hidden from Browse Cards / search
(products/views.py), never carry a tcgcsv_product_id (so the nightly card
price sync can't touch them) and have no card_set (so checklists, Pokedex and
Poke-Trade never see them).
"""
from django.db import transaction
from django.db.models import F, OuterRef, Subquery

ACCESSORY_SUPERTYPE = "Accessory"


def _category():
    from products.models import Category
    return Category.objects.get_or_create(name="Accessories", defaults={"slug": "accessories"})[0]


def refresh_accessory_stock():
    """Copy the live (product) stock back onto every linked accessory."""
    from products.models import PokemonProduct
    from .models import Accessory
    live = PokemonProduct.objects.filter(pk=OuterRef("cart_product_id")).values("stock")[:1]
    Accessory.objects.filter(cart_product__isnull=False).exclude(stock=F("cart_product__stock")).update(stock=Subquery(live))


def push_to_product(acc, stock_delta=None, set_stock=False):
    """Create/update the accessory's product row.
    stock_delta: add this many to the product stock (buying invoice).
    set_stock:   make the product stock equal acc.stock (staff edited it)."""
    from products.models import PokemonProduct
    from .models import Accessory

    fields = dict(
        name=acc.name[:200],
        price=acc.price,
        price_normal=acc.price,
        image_url=acc.image_url or "",
        image_small_url=acc.image_url or "",
        description=acc.description or "",
        is_active=acc.is_active,
    )
    with transaction.atomic():
        prod = PokemonProduct.objects.select_for_update().filter(pk=acc.cart_product_id).first() if acc.cart_product_id else None
        if prod is None:
            prod = PokemonProduct(
                pb_id=f"ACC-{acc.pk}", supertype=ACCESSORY_SUPERTYPE, variant_override="N",
                condition="NM", rarity="common", category=_category(), stock=acc.stock, **fields,
            )
            prod.save()
            Accessory.objects.filter(pk=acc.pk).update(cart_product=prod)
            acc.cart_product_id = prod.pk
            return prod
        PokemonProduct.objects.filter(pk=prod.pk).update(**fields)
        if stock_delta:
            PokemonProduct.objects.filter(pk=prod.pk).update(stock=F("stock") + stock_delta)
        elif set_stock:
            PokemonProduct.objects.filter(pk=prod.pk).update(stock=acc.stock)
    return prod
