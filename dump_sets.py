import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import CardSet, Era

print(f"{'ERA_CODE':<12} {'SET_CODE':<15} {'RELEASE':<12} SET_NAME")
print('-'*70)
for s in CardSet.objects.select_related('era').order_by('era__code', 'release_date'):
    era_code = s.era.code if s.era else '?'
    print(f"{era_code:<12} {s.code:<15} {str(s.release_date or ''):<12} {s.name}")

print()
print('ERAS:')
for e in Era.objects.all().order_by('code'):
    count = CardSet.objects.filter(era=e).count()
    print(f'  {e.code:<12} | {e.name:<30} | {count} sets')
