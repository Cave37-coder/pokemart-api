import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Q
from products.models import PokemonProduct, CardSet

# Read-only. Scoping the SWSH-era booster sets (NOT the SWSH promos, which
# are already done) before building a Serebii fetch script -- need to know
# this catalog's actual CardSet.code for each one, since Serebii names
# ("Rebel Clash", "Darkness Ablaze", etc.) won't necessarily match the
# short codes used here.

SWSH_SET_NAMES = [
    "Sword", "Shield", "Rebel Clash", "Darkness Ablaze", "Vivid Voltage",
    "Shining Fates", "Battle Styles", "Chilling Reign", "Evolving Skies",
    "Fusion Strike", "Brilliant Stars", "Astral Radiance", "Pokemon GO",
    "Lost Origin", "Silver Tempest", "Crown Zenith",
]

q = Q()
for name in SWSH_SET_NAMES:
    q |= Q(name__icontains=name)

sets = CardSet.objects.filter(q).order_by('code')

print(f"{'Code':10} {'Era':8} {'Name':35} {'Active':>7} {'Blank img':>10}")
print("-" * 80)
for cs in sets:
    products = PokemonProduct.objects.filter(card_set=cs, is_active=True)
    active = products.count()
    if active == 0:
        continue
    blank = products.filter(Q(image_url='') | Q(image_url__isnull=True)).count()
    era_code = cs.era.code if getattr(cs, 'era', None) else '?'
    print(f"{cs.code:10} {era_code:8} {cs.name[:35]:35} {active:>7} {blank:>10}")

print()
print("NOTE: 'blank img' undercounts broken images (a stored URL can still 404")
print("or point at the wrong card) -- same caveat as every prior image audit.")
