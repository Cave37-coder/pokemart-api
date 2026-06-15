# Add variant_sort field to PokemonProduct model
# This needs to be added to products/models.py and then migrated
# Run: python manage.py shell --command="exec(open('add_variant_sort_migration.py').read())"

# First check if field already exists in model
from products.models import PokemonProduct
fields = [f.name for f in PokemonProduct._meta.get_fields()]
print("Current fields:", 'variant_sort' in fields)

# Check if column exists in DB
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='products_pokemonproduct' AND column_name='variant_sort'
    """)
    exists = cursor.fetchone()
    print("DB column exists:", bool(exists))
