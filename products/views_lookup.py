# pokemart-api: products/views_lookup.py — v1.7.0
# v1.7.0: card_lookup (exact-SKU) now also returns variant, matching
# card_search — condition is effectively a no-op across this dataset
# (defaults to NM almost everywhere and was never meaningfully set
# otherwise), variant is the real distinguishing field and must be
# surfaced by every endpoint touching PokemonProduct.
# v1.6.0: added variant_override to search results — without it, two
# rows for the same card_number but different variants (Normal vs
# Reverse Holo etc) looked like exact duplicates with no way to tell
# them apart, since only the price differed.
# v1.5.0: card_search now matches across name, set name, set code, AND
# card number together — not just name. A search like "gastly sf" or
# "gastly 62" now actually narrows results, instead of every Gastly ever
# printed competing for the same 20-result cap. Query is split into words;
# every word must match somewhere across those four fields (order-independent),
# so "sf gastly" and "gastly sf" both work the same way.

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from .models import PokemonProduct


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
        "variant": product.variant_override or None,
        "price": product.price,
    })


@api_view(["GET"])
def card_search(request):
    """GET /api/cards/search/?q=gastly+sf
    Called by PoBuSA's buy-in screen — returns NM cards matching every word
    in the query, checked against name, set name, set code, and card
    number together. Lets staff narrow down a common name like "Gastly"
    by adding a set hint ("gastly sf") or card number ("gastly 62").
    Read-only. Capped at 30 results; total_matches tells the frontend if
    there are more than that so it can prompt for a narrower search."""
    query = request.query_params.get("q", "").strip()
    if not query:
        return Response({"results": [], "total_matches": 0})

    words = query.split()
    queryset = PokemonProduct.objects.select_related("card_set").filter(condition="NM", is_active=True)

    for word in words:
        queryset = queryset.filter(
            Q(name__icontains=word)
            | Q(card_set__name__icontains=word)
            | Q(card_set__code__icontains=word)
            | Q(card_number__iexact=word)
        )

    total_matches = queryset.count()
    products = queryset.order_by("name")[:30]

    results = [
        {
            "sku": p.sku,
            "name": p.name,
            "set": p.card_set.name if p.card_set else None,
            "set_code": p.card_set.code if p.card_set else None,
            "number": p.card_number,
            "variant": p.variant_override or None,
            "price": p.price,
        }
        for p in products
    ]
    return Response({"results": results, "total_matches": total_matches})
