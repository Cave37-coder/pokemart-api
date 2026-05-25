from products.models import PokemonProduct

for code in ['WHT', 'BLK']:
    total = PokemonProduct.objects.filter(card_set__code=code).count()
    active = PokemonProduct.objects.filter(card_set__code=code, is_active=True).count()
    inactive = PokemonProduct.objects.filter(card_set__code=code, is_active=False).count()
    no_image = PokemonProduct.objects.filter(card_set__code=code, image_url='').count()
    variants = PokemonProduct.objects.filter(card_set__code=code).values_list('variant_override', flat=True).distinct()
    print(f"{code}: total={total} active={active} inactive={inactive} no_image={no_image}")
    print(f"  variants: {sorted(set(variants))}")
