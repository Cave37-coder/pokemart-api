import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from products.models import PokemonProduct, CardSet
# All distinct set codes that have ANY cards, in B7 era
sets = CardSet.objects.filter(era__code='B7')
for s in sets.order_by('release_date'):
    count = PokemonProduct.objects.filter(card_set=s).count()
    print(s.code + ' | ' + s.name + ' | ' + str(count) + ' cards')
