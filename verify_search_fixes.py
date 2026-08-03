# PokeBulk SA -- verifies the two search-related fixes/questions:
#
# 1) Did today's pokedex_number backfill actually move the needle on the
#    original "pikachu search finds only 124 of 286" symptom?
# 2) Does DRF's SearchFilter (icontains) actually behave sanely on the
#    integer fields (pokedex_number, card_number) in search_fields, or does
#    it silently misbehave / do something surprising?
#
# Read-only -- makes no DB changes. Safe to run any time.
#
# Usage:
#   python verify_search_fixes.py

import django, os, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
# RequestFactory's fake requests come in with Host: testserver -- allow it
# for this read-only diagnostic run so we can exercise the real view code
# (pagination etc) without touching ALLOWED_HOSTS in the actual settings file.
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.test import RequestFactory
from products.models import PokemonProduct
from products.views import PokemonProductViewSet


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main():
    section("1) Pikachu: name-match vs pokedex_number=25 (post-backfill)")
    name_matches = PokemonProduct.objects.filter(is_active=True, name__icontains="pikachu")
    total = name_matches.count()
    tagged = name_matches.filter(pokedex_number=25).count()
    print(f"Active products with 'pikachu' in the name: {total}")
    print(f"  of those, pokedex_number = 25:            {tagged}")
    print(f"  of those, pokedex_number != 25 or NULL:    {total - tagged}")
    if total - tagged:
        mismatches = name_matches.exclude(pokedex_number=25)
        print("\n  Remaining mismatches -- showing supertype/hp/is_active so we can see")
        print("  WHY the backfill's queryset never picked these up (it only targeted")
        print("  supertype in {Basic,Stage 1,Stage 2,Pokemon,VMAX,VSTAR,bASIC,2} or")
        print("  blank-supertype-with-hp-set):")
        for p in mismatches[:30]:
            print(f"    id={p.id} {p.name!r} supertype={p.supertype!r} hp={p.hp!r} "
                  f"pokedex_number={p.pokedex_number} is_active={p.is_active}")

        print("\n  Breakdown of ALL mismatches by supertype (to spot the real pattern):")
        from django.db.models import Count
        for row in mismatches.values('supertype').annotate(n=Count('id')).order_by('-n'):
            print(f"    supertype={row['supertype']!r}: {row['n']}")

    section("2) Does the live /api/products/?pokedex=0025 filter improve?")
    factory = RequestFactory()
    view = PokemonProductViewSet.as_view({'get': 'list'})
    request = factory.get('/api/products/', {'pokedex': '0025', 'page_size': '1'})
    response = view(request)
    response.render() if hasattr(response, 'render') else None
    count = None
    try:
        count = response.data.get('count')
    except Exception as e:
        count = f"<could not read count: {e}>"
    print(f"GET /api/products/?pokedex=0025 -> reported count: {count}")

    section("3) SearchFilter icontains behaviour on integer fields")
    exact_25 = PokemonProduct.objects.filter(is_active=True, pokedex_number=25).count()
    try:
        icontains_25 = PokemonProduct.objects.filter(is_active=True, pokedex_number__icontains='25').count()
        print(f"pokedex_number = 25 (exact):      {exact_25}")
        print(f"pokedex_number__icontains '25':   {icontains_25}")
        if icontains_25 != exact_25:
            print(f"  -> icontains matches MORE/FEWER rows than exact -- it's substring-")
            print(f"     matching the number as text (e.g. would also match 125, 250,")
            print(f"     251-259 etc), not doing what a user probably expects.")
        else:
            print("  -> icontains and exact returned the same count for this value.")
    except Exception as e:
        print(f"pokedex_number__icontains RAISED AN ERROR: {type(e).__name__}: {e}")
        print("  -> this confirms integer fields in search_fields are broken.")

    section("4) Live search endpoint: /api/products/?search=Pikachu")
    request2 = factory.get('/api/products/', {'search': 'Pikachu', 'page_size': '1'})
    response2 = view(request2)
    response2.render() if hasattr(response2, 'render') else None
    try:
        count2 = response2.data.get('count')
    except Exception as e:
        count2 = f"<could not read count: {e}>"
    print(f"GET /api/products/?search=Pikachu -> reported count: {count2}")
    print(f"(compare to the {total} active products with 'pikachu' in the name, from step 1)")


if __name__ == "__main__":
    main()
