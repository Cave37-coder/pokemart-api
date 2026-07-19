"""
audit_image_gaps.py
Read-only. For every CardSet, reports how many cards have a blank
image_url vs. a populated one -- AND samples actual URL values per set,
since broken-image icons (vs. the site's normal card-emoji placeholder
for genuinely blank URLs) suggest URLs are POPULATED but pointing at
dead links, not blank. Blank-only counting would completely miss that.

Usage:
    python manage.py shell -c "exec(open('audit_image_gaps.py').read())"
"""

from products.models import PokemonProduct, CardSet
from django.db.models import Q

print("Auditing image_url per set (blank counts + sample real URLs)...")
print()

rows = []
for cs in CardSet.objects.all().order_by('era__code', 'code'):
    products = PokemonProduct.objects.filter(card_set=cs)
    total = products.count()
    if total == 0:
        continue

    missing = products.filter(Q(image_url='') | Q(image_url__isnull=True)).count()
    sample = products.exclude(Q(image_url='') | Q(image_url__isnull=True)).values_list('image_url', flat=True).first()

    rows.append({
        'era': cs.era.code if cs.era else '?',
        'code': cs.code,
        'name': cs.name,
        'total': total,
        'missing': missing,
        'missing_pct': missing / total * 100 if total else 0,
        'sample_url': sample,
    })

rows.sort(key=lambda r: -r['missing'])

print(f"{'Era':8} {'Set':8} {'Cards':>7} {'Blank':>7} {'%':>5}  Sample URL (if any)")
print("-" * 100)
grand_total_missing = 0
for r in rows:
    if r['missing'] > 0 or r['sample_url']:
        print(f"{r['era']:8} {r['code']:8} {r['total']:>7} {r['missing']:>7} {r['missing_pct']:>4.0f}%  {r['sample_url'] or '(no sample)'}")
    grand_total_missing += r['missing']

print()
print(f"Total cards with genuinely BLANK image_url sitewide: {grand_total_missing:,}")
print()
print("IMPORTANT: a low/zero blank count for a set does NOT mean its images work --")
print("it just means a URL string is stored. Check the sample URLs above for any set")
print("showing broken images on-screen (like WotC/BSS) -- if the domain/path looks")
print("wrong or dead, that's the real bug, and this script can't detect that from")
print("the DB alone without making a live HTTP request per URL.")
