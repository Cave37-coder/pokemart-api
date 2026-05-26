from products.models import PokemonProduct

# Check what variant codes exist in DB
variants = PokemonProduct.objects.values_list('variant_override', flat=True).distinct().order_by('variant_override')
print("All variant codes in DB:")
for v in variants:
    count = PokemonProduct.objects.filter(variant_override=v).count()
    print(f"  '{v}': {count}")
