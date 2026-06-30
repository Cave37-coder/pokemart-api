from products.models import PokemonProduct
from urllib.parse import urlparse
from collections import Counter

qs = PokemonProduct.objects.exclude(image_url='').values_list('image_url', 'card_set__code')
total_with_image = qs.count()
total_all = PokemonProduct.objects.count()
blank_image = PokemonProduct.objects.filter(image_url='').count()

print(f"Total products: {total_all}")
print(f"  With image_url: {total_with_image}")
print(f"  Blank image_url: {blank_image}")

host_counts = Counter()
host_by_set = {}
for url, set_code in qs:
    host = urlparse(url).netloc
    host_counts[host] += 1
    host_by_set.setdefault(host, Counter())[set_code or 'NONE'] += 1

print(f"\n--- Breakdown by image host ({len(host_counts)} distinct hosts) ---")
for host, count in host_counts.most_common(20):
    print(f"  {host}: {count}")

print("\n--- Top sets for each non-R2 host (likely candidates for migration) ---")
for host, count in host_counts.most_common(20):
    if 'pokebulk.co.za' in host:
        continue
    top_sets = host_by_set[host].most_common(5)
    print(f"  {host} ({count} total) — top sets: {top_sets}")
