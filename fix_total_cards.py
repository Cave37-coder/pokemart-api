import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import CardSet
from django.db.models import Count

sets = CardSet.objects.annotate(pc=Count('products')).all()
updated = 0
for s in sets:
    if s.total_cards != s.pc:
        s.total_cards = s.pc
        s.save(update_fields=['total_cards'])
        updated += 1
        print(f'{s.code}: {s.total_cards}')
print(f'Done. Updated {updated} sets.')

