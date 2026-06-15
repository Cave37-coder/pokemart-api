import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import PokemonProduct, CardSet
for s in CardSet.objects.select_related('era').order_by('era__code', 'release_date'):
    count = PokemonProduct.objects.filter(card_set=s).count()
    era = s.era.code if s.era else 'NO_ERA'
    print(era + ' | ' + s.code + ' | ' + s.name + ' | ' + str(count))
