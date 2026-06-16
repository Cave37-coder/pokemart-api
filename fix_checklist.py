content = open('C:/Users/texca/pokemart-api/products/views.py', encoding='utf-8').read()

extra = "\n\nfrom django.http import JsonResponse\nfrom django.views.decorators.http import require_GET\n\n@require_GET\ndef checklist_stock(request):\n    raw = request.GET.get('product_ids', '')\n    if not raw:\n        return JsonResponse([], safe=False)\n    try:\n        pids = [int(p.strip()) for p in raw.split(',') if p.strip().isdigit()]\n    except ValueError:\n        return JsonResponse({'error': 'Invalid'}, status=400)\n    if not pids:\n        return JsonResponse([], safe=False)\n    pids = pids[:1000]\n    from products.models import PokemonProduct\n    in_stock = list(PokemonProduct.objects.filter(product_id__in=pids, stock_quantity__gt=0).values_list('product_id', flat=True))\n    return JsonResponse(in_stock, safe=False)\n"

open('C:/Users/texca/pokemart-api/products/views.py', 'w', encoding='utf-8').write(content + extra)
print('views.py done')

urls = open('C:/Users/texca/pokemart-api/products/urls.py', encoding='utf-8').read()
urls = urls.replace('path("checklists/stock/", views.checklist_stock', 'path("checklists/stock-check/", views.checklist_stock')
open('C:/Users/texca/pokemart-api/products/urls.py', 'w', encoding='utf-8').write(urls)
print('urls.py done')
