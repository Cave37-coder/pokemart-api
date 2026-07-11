# pokemart-api: cards/views_lookup.py — v1.0.0
# Lightweight read-only endpoint for PoBuSA to look up a single card by SKU.
# Returns structural info (name/set/number) + the current synced price.
# Never writes anything — read-only, no stock/order side effects.
#
# ASSUMPTIONS TO VERIFY against your actual models (products/models.py):
#   - Model name: PokemonProduct (per condition-system work from June 2026)
#   - SKU field: assumed "sku" — confirm actual field name
#   - Price field: assumed "price" on the product/variant — this is the same
#     field sync_prices.py / sync_tcgcsv.py already populates from TCGCSV,
#     but the exact field name was flagged as unverified in past sessions
#     ("variant.price field name remains a placeholder to verify")
#   - Set name field: assumed accessible via product.set.name or similar FK
#
# Adjust the field names in card_lookup() below to match your real model,
# then this is a straight drop-in.

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import PokemonProduct  # adjust import path if products app is named differently


@api_view(["GET"])
def card_lookup(request):
    """GET /api/cards/lookup/?sku=sv09-074-rev
    Called by PoBuSA (pobusa/services.py fetch_card_data). Read-only."""
    sku = request.query_params.get("sku")
    if not sku:
        return Response({"error": "sku is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        product = PokemonProduct.objects.get(sku=sku)  # VERIFY: actual SKU field name
    except PokemonProduct.DoesNotExist:
        return Response({"error": f"Card {sku} not found"}, status=status.HTTP_404_NOT_FOUND)

    # VERIFY: actual field names for name/set/number/price on your model
    return Response({
        "name": product.name,
        "set": product.set.name if hasattr(product, "set") else None,
        "number": getattr(product, "number", None),
        "price": product.price,  # this must be the TCGCSV-synced price field
    })
