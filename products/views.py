from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page
from products.models import PokemonProduct


@require_GET
@cache_page(60 * 5)  # cache 5 minutes
def checklist_stock(request):
    """
    GET /api/checklists/stock/?product_ids=123,456,789
    Returns list of product_ids that have stock_quantity > 0.
    Used by the frontend checklist page to show/hide Buy links.
    """
    raw = request.GET.get('product_ids', '')
    if not raw:
        return JsonResponse([], safe=False)

    try:
        pids = [int(p.strip()) for p in raw.split(',') if p.strip().isdigit()]
    except ValueError:
        return JsonResponse({'error': 'Invalid product_ids'}, status=400)

    if not pids:
        return JsonResponse([], safe=False)

    # Cap at 1000 to prevent abuse
    pids = pids[:1000]

    in_stock = list(
        PokemonProduct.objects
        .filter(product_id__in=pids, stock_quantity__gt=0)
        .values_list('product_id', flat=True)
    )

    return JsonResponse(in_stock, safe=False)
