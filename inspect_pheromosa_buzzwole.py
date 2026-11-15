
# Read-only diagnostic v2: the first pass showed ZERO owned entries for
# pokebulk77@gmail.com (id=3) even though the live site (logged in as
# "CaVe37") shows Pheromosa/Buzzwole as caught. That means either a
# different account owns these, or the toggle never actually persisted.
# This version doesn't guess the email -- it finds every account that has
# ANY owned entry among the 794/795 products, so we can see who actually
# owns what.

import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Q
from products.models import PokemonProduct, PokedexCollectionEntry
from django.contrib.auth import get_user_model

User = get_user_model()

print("=== Users matching 'CaVe37' or similar ===")
for u in User.objects.filter(Q(username__icontains='cave37') | Q(email__icontains='cave') | Q(first_name__icontains='cave')):
    print(f"  id={u.id} username={getattr(u, 'username', None)!r} email={u.email!r}")

print("\n=== All active products tied to dex 794/795 ===")
qs = PokemonProduct.objects.filter(is_active=True).filter(
    Q(pokedex_number__in=[794, 795]) | Q(pokedex_number_2__in=[794, 795])
)
print(f"  ({qs.count()} products)")

print("\n=== EVERY owned entry (any user) among those products ===")
owned = PokedexCollectionEntry.objects.filter(product__in=qs).select_related('product', 'user').order_by('user_id', '-added_at')
if not owned:
    print("  *** NONE. Nobody owns any of these products in the DB. ***")
for e in owned:
    p = e.product
    print(f"  user_id={e.user_id} username={getattr(e.user, 'username', None)!r} email={e.user.email!r}")
    print(f"      product_id={p.id} pn={p.pokedex_number} pn2={p.pokedex_number_2} price={p.price} name={p.name!r} added_at={e.added_at}")

print("\n=== Total PokedexCollectionEntry rows in the whole table (sanity check) ===")
print(f"  {PokedexCollectionEntry.objects.count()} total rows across all users/products")
