"""
Add legality fields to PokemonProduct model via raw SQL then fake migration.
Run: python manage.py shell --command="exec(open('add_legality_fields.py').read())"
"""
from django.db import connection

fields = {
    'legal_standard': 'BOOLEAN DEFAULT NULL',
    'legal_expanded': 'BOOLEAN DEFAULT NULL', 
    'legal_unlimited': 'BOOLEAN DEFAULT TRUE',
}

for field, definition in fields.items():
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='products_pokemonproduct' AND column_name='{field}'
        """)
        exists = cursor.fetchone()
    
    if not exists:
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE products_pokemonproduct ADD COLUMN {field} {definition}")
        print(f"Added {field}")
    else:
        print(f"{field} already exists")

print("Done!")
