"""
Check ID fields on a sample of cards
Run: python manage.py shell --command="exec(open('check_ids.py').read())"
"""
from products.models import PokemonProduct

# Check a sample from different sets
sets = ['ASC', 'CRI', 'SVI', 'SWSH01', 'SM01']
for code in sets:
    cards = PokemonProduct.objects.filter(
        card_set__code=code
    ).values(
        'name', 'card_number', 'variant_override',
        'tcgcsv_product_id', 'tcgplayer_id', 'gengar_id'
    ).order_by('card_number')[:3]
    
    print(f"\n{code}:")
    for c in cards:
        print(f"  #{c['card_number']} {c['variant_override']:<6} {c['name'][:25]:<25} tcgcsv={c['tcgcsv_product_id']} tcgplayer={c['tcgplayer_id']} gengar={c['gengar_id']}")
