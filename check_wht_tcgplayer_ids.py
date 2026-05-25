from products.models import PokemonProduct

# Check tcgplayer_id (pokemontcg.io ID) for WHT vs BLK
print("WHT sample tcgplayer_ids:")
wht = PokemonProduct.objects.filter(card_set__code='WHT').exclude(tcgplayer_id='').exclude(tcgplayer_id__isnull=True).values('card_number','variant_override','tcgplayer_id','image_url')[:5]
for r in wht:
    print(f"  #{r['card_number']} {r['variant_override']} tcgplayer_id={r['tcgplayer_id']} has_image={'YES' if r['image_url'] else 'NO'}")

print("\nBLK sample tcgplayer_ids:")
blk = PokemonProduct.objects.filter(card_set__code='BLK').exclude(tcgplayer_id='').exclude(tcgplayer_id__isnull=True).values('card_number','variant_override','tcgplayer_id','image_url')[:5]
for r in blk:
    print(f"  #{r['card_number']} {r['variant_override']} tcgplayer_id={r['tcgplayer_id']} has_image={'YES' if r['image_url'] else 'NO'}")

# Check WHT records without images
no_img = PokemonProduct.objects.filter(card_set__code='WHT', image_url='').count()
with_img = PokemonProduct.objects.filter(card_set__code='WHT').exclude(image_url='').count()
print(f"\nWHT: {with_img} with image, {no_img} without image")
