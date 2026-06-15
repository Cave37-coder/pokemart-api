from products.models import PokemonProduct
cards = PokemonProduct.objects.filter(card_set__code='ASC', stock__gt=0).values(
    'card_number','variant_override','stock','tcgcsv_product_id','name'
).order_by('card_number','variant_override')
print(f"ASC records with stock > 0: {cards.count()}")
for c in cards:
    num = str(c['card_number']).zfill(3)
    print(f"  #{num} {c['variant_override']:<10} stock={c['stock']} pid={c['tcgcsv_product_id']} {c['name'][:35]}")
