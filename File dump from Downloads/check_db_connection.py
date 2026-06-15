"""
Check which DB is active and test a direct insert
Run: python manage.py shell --command="exec(open('check_db_connection.py').read())"
"""
from django.db import connections
from django.conf import settings
from products.models import PokemonProduct, CardSet

# Show DB config
print("DB connections:")
for alias, config in settings.DATABASES.items():
    host = config.get('HOST', 'N/A')
    name = config.get('NAME', 'N/A')
    print(f"  {alias}: host={host} name={name}")

# Count before
before = PokemonProduct.objects.count()
print(f"\nProducts before: {before}")

# Try a direct save
cs = CardSet.objects.get(code='ASRTG')
print(f"CardSet ASRTG: id={cs.id} era={cs.era_id}")

# Try creating one product directly
try:
    from products.models import Category
    cat, _ = Category.objects.get_or_create(name="Pokemon")
    p = PokemonProduct(
        pb_id="ASRTG-TEST-H",
        tcgcsv_product_id=999999,
        name="Test Card",
        card_number=99,
        card_set=cs,
        category=cat,
        variant_override="H",
        rarity="common",
        price=5.00,
        stock=0,
        is_active=True,
    )
    p.save()
    after = PokemonProduct.objects.count()
    print(f"Products after test save: {after}")
    print(f"Test card saved: pb_id={p.pb_id} id={p.id}")
    # Clean up
    p.delete()
    print(f"Test card deleted. Products now: {PokemonProduct.objects.count()}")
except Exception as e:
    print(f"ERROR: {e}")
