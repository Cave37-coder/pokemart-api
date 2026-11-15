import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Q
from products.models import PokemonProduct, CardSet

# Read-only. Michael: "Can we do the image download for WOTC, Neo, Legendary,
# e-Card and EX era" -- before building the fetch script, need the real
# CardSet codes in THIS catalog for each set, since Serebii's set names
# won't necessarily match this DB's short codes (same reason list_swsh_sets.py
# and list_promo_sets.py existed).
#
# Serebii slugs already confirmed by reading serebii.net/card/first.shtml,
# neo.shtml, and ex.shtml directly (not guessed):
#   WOTC:      Base, Jungle, Fossil, Team Rocket, Gym Heroes, Gym Challenge
#   Neo:       Neo Genesis, Neo Discovery, Neo Revelation, Neo Destiny
#   e-Card:    Expedition, Aquapolis, Skyridge
#   Legendary: Legendary Collection (Serebii just calls it "Legendary")
#   EX:        EX Ruby & Sapphire through EX Power Keepers (16 sets)

CLASSIC_SET_NAMES = [
    "Base Set", "Base", "Jungle", "Fossil", "Team Rocket",
    "Gym Heroes", "Gym Challenge",
    "Neo Genesis", "Neo Discovery", "Neo Revelation", "Neo Destiny",
    "Expedition", "Aquapolis", "Skyridge",
    "Legendary Collection",
    "EX Ruby", "EX Sandstorm", "EX Dragon", "EX Team Magma", "EX Hidden Legends",
    "EX FireRed", "EX Team Rocket Returns", "EX Deoxys", "EX Emerald",
    "EX Unseen Forces", "EX Delta Species", "EX Legend Maker", "EX Holon Phantoms",
    "EX Crystal Guardians", "EX Dragon Frontiers", "EX Power Keepers",
]

q = Q()
for name in CLASSIC_SET_NAMES:
    q |= Q(name__icontains=name)

sets = CardSet.objects.filter(q).order_by('code')

print(f"{'Code':12} {'Era':8} {'Name':38} {'Active':>7} {'Blank img':>10}")
print("-" * 82)
seen_ids = set()
for cs in sets:
    if cs.id in seen_ids:
        continue
    seen_ids.add(cs.id)
    products = PokemonProduct.objects.filter(card_set=cs, is_active=True)
    active = products.count()
    if active == 0:
        continue
    blank = products.filter(Q(image_url='') | Q(image_url__isnull=True)).count()
    era_code = cs.era.code if getattr(cs, 'era', None) else '?'
    print(f"{cs.code:12} {era_code:8} {cs.name[:38]:38} {active:>7} {blank:>10}")

print()
print("NOTE: 'blank img' undercounts broken images (a stored URL can still 404")
print("or point at the wrong card) -- same caveat as every prior image audit.")
print()
print("If 'Legendary Collection' doesn't show up above, tell me what its actual")
print("name/code is in the catalog so I can add it to the match list.")
