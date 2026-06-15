import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct
from django.db.models import Count

# Check variant breakdown for ASC
print("ASC variant breakdown:")
qs = PokemonProduct.objects.filter(card_set__code='ASC').values('variant_override').annotate(count=Count('id')).order_by('-count')
for v in qs:
    print(f"  {repr(v['variant_override'])}: {v['count']}")

print()
print("ASC sample records:")
for p in PokemonProduct.objects.filter(card_set__code='ASC').order_by('card_number', 'variant_sort')[:20]:
    print(f"  #{p.card_number} | vo={repr(p.variant_override)} | vs={p.variant_sort} | {p.name[:60]}")

print()
# Check ex in SV era
print("SV era ex sample:")
sv_ex = PokemonProduct.objects.filter(card_set__era__code='SV', name__icontains=' ex').values('name', 'variant_override')[:10]
for p in sv_ex:
    print(f"  vo={repr(p['variant_override'])} | {p['name'][:60]}")

print()
print("MEG era ex sample:")
meg_ex = PokemonProduct.objects.filter(card_set__era__code='MEG', name__icontains=' ex').values('name', 'variant_override')[:10]
for p in meg_ex:
    print(f"  vo={repr(p['variant_override'])} | {p['name'][:60]}")
