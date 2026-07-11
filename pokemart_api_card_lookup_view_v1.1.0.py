# pokemart-api: cards/views_lookup.py — v1.1.0
# Lightweight read-only endpoint for PoBuSA to look up a single card by SKU.
# Returns structural info (name/set/number) + the current synced price.
# Never writes anything — read-only, no stock/order side effects.
#
# Field names confirmed against the real PokemonProduct model:
#   sku, name, card_set (FK -> CardSet.name), card_number, price

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import PokemonProduct  # adjust import path if this file doesn't live in the same app


@api_view(["GET"])
def card_lookup(request):
    """GET /api/cards/lookup/?sku=sv09-074-rev
    Called by PoBuSA (pobusa/services.py fetch_card_data). Read-only.

    Note: PokemonProduct stores one row per condition (see the +Played stock
    entry flow), so a played copy's SKU is a distinct row with its own price.
    If PoBuSA should always reference the NM/base price regardless of the
    condition being bought in, the lookup may need to resolve to the NM row
    specifically rather than whatever SKU is passed — flag if that's the case,
    since right now this returns whatever row matches the SKU exactly."""
    sku = request.query_params.get("sku")
    if not sku:
        return Response({"error": "sku is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        product = PokemonProduct.objects.select_related("card_set").get(sku=sku)
    except PokemonProduct.DoesNotExist:
        return Response({"error": f"Card {sku} not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "name": product.name,
        "set": product.card_set.name if product.card_set else None,
        "number": product.card_number,
        "price": product.price,
    })
