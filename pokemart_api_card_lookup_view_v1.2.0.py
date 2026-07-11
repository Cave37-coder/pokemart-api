# pokemart-api: cards/views_lookup.py — v1.2.0
# Lightweight read-only endpoint for PoBuSA to look up a single card by SKU.
# Returns structural info (name/set/number) + the current synced price.
# Never writes anything — read-only, no stock/order side effects.
#
# Field names confirmed against the real PokemonProduct model:
#   sku, name, card_set (FK -> CardSet.name), card_number, price
#
# v1.2.0: confirmed rule — condition is entirely a PoBuSA/staff-discretion
# field, never API-based. market_ref always resolves to the NM row's price,
# regardless of what condition the physical card being bought in actually
# is. Explicitly filters condition="NM" so a played-copy row with the same
# base SKU (or a near-duplicate SKU) can never leak its discounted price
# into a buy-in calculation.

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import PokemonProduct  # adjust import path if this file doesn't live in the same app


@api_view(["GET"])
def card_lookup(request):
    """GET /api/cards/lookup/?sku=sv09-074-rev
    Called by PoBuSA (pobusa/services.py fetch_card_data). Read-only.
    Always returns the NM row's price as market_ref — condition is decided
    by staff on the PoBuSA side, not looked up here."""
    sku = request.query_params.get("sku")
    if not sku:
        return Response({"error": "sku is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        product = PokemonProduct.objects.select_related("card_set").get(sku=sku, condition="NM")
    except PokemonProduct.DoesNotExist:
        return Response({"error": f"NM card {sku} not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "name": product.name,
        "set": product.card_set.name if product.card_set else None,
        "number": product.card_number,
        "price": product.price,
    })
