from products.models import PokemonProduct

# Check BLK records - how many have images vs not
total = PokemonProduct.objects.filter(card_set__code='BLK').count()
with_image = PokemonProduct.objects.filter(card_set__code='BLK').exclude(image_url='').exclude(image_url__isnull=True).count()
no_image = PokemonProduct.objects.filter(card_set__code='BLK').filter(image_url='').count()

print(f"BLK total records: {total}")
print(f"With image: {with_image}")
print(f"No image: {no_image}")

# Show sample of records without images
missing = PokemonProduct.objects.filter(card_set__code='BLK', image_url='').values('card_number','variant_override','name')[:10]
print(f"\nSample missing images:")
for r in missing:
    print(f"  #{str(r['card_number']).zfill(3)} {r['variant_override']:<10} {r['name'][:30]}")
