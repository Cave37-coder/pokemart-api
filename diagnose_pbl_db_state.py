from products.models import PokemonProduct, CardSet
from collections import Counter

pbl = CardSet.objects.get(code='PBL')
products = list(PokemonProduct.objects.filter(card_set=pbl))

print(f"Total PokemonProduct rows for PBL: {len(products)}")
print(f"(Expected 194 if the sync worked correctly, 120 if the pb_id bug collapsed variants)")
print()

variant_counts = Counter(p.variant_override for p in products)
print("variant_override breakdown:")
for v, c in sorted(variant_counts.items()):
    print(f"  {v}: {c}")

print()
pb_id_counts = Counter(p.pb_id for p in products)
dupes = {k: v for k, v in pb_id_counts.items() if v > 1}
print(f"Duplicate pb_id values (should be 0): {len(dupes)}")

print()
print("Sample of first 10 rows (id, pb_id, card_number, name, variant_override, price, image_url):")
for p in sorted(products, key=lambda x: (x.card_number or 0))[:10]:
    print(f"  id={p.id} pb_id={p.pb_id} #{p.card_number} {p.name!r} variant={p.variant_override} price={p.price} image={'yes' if p.image_url else 'NONE'}")
