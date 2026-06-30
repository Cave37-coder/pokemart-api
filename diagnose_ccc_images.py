from products.models import PokemonProduct, CardSet

ccc = CardSet.objects.get(code='CCC')
products = PokemonProduct.objects.filter(card_set=ccc)
print(f"Total CCC products: {products.count()}")

print("\n--- Sample of 15 image_url values ---")
for p in products[:15]:
    print(f"  id={p.id} pb_id={p.pb_id} name={p.name!r}")
    print(f"      image_url={p.image_url!r}")

print("\n--- Breakdown by image host ---")
from urllib.parse import urlparse
from collections import Counter
hosts = Counter(urlparse(p.image_url).netloc if p.image_url else 'BLANK' for p in products)
for host, count in hosts.most_common():
    print(f"  {host}: {count}")
