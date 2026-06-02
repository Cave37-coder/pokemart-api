import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import CardSet, Era
print('=== ERAS ===')
for e in Era.objects.all().order_by('code'):
    print(str(e.id) + ' | ' + e.code + ' | ' + e.name)
print('')
print('=== SETS ===')
for s in CardSet.objects.select_related('era').order_by('era__code', 'release_date'):
    era_code = s.era.code if s.era else 'NO_ERA'
    print(era_code + ' | ' + s.code + ' | ' + s.name)
