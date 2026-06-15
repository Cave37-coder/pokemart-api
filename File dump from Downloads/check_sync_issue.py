"""
Check why synced sets show 0 products
Run: python manage.py shell --command="exec(open('check_sync_issue.py').read())"
"""
from products.models import PokemonProduct, CardSet

# Check a few of the problem sets
check_sets = ['ASRTG', 'TOT22', 'MEE', 'RUM', 'DEP']

for code in check_sets:
    try:
        cs = CardSet.objects.get(code=code)
        count = PokemonProduct.objects.filter(card_set=cs).count()
        # Check if any products exist with this set's pb_id pattern
        pb_pattern = PokemonProduct.objects.filter(pb_id__startswith=f"{code}-").count()
        # Check for any product with this card_set id
        print(f"{code}: CardSet id={cs.id} name='{cs.name}' | by card_set={count} | by pb_id={pb_pattern}")
    except CardSet.DoesNotExist:
        print(f"{code}: NO CARDSET")

# Also check if there are any products with card_set=None
none_count = PokemonProduct.objects.filter(card_set__isnull=True).count()
print(f"\nProducts with no card_set: {none_count}")

# Check total products
total = PokemonProduct.objects.count()
print(f"Total products in DB: {total}")
