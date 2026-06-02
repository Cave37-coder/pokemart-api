import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import CardSet
swsh = CardSet.objects.filter(era__code='B7').order_by('release_date')
for s in swsh:
    print(s.code + ' | ' + s.name + ' | ' + str(s.release_date))
