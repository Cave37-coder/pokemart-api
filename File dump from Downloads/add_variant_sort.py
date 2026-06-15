# Update all records with variant_sort values based on variant_override
# Run: python manage.py shell --command="exec(open('add_variant_sort.py').read())"

from django.db import connection

VARIANT_ORDER = {
    'N': 0, '1E': 0, 'SH': 0,
    'H': 1, '1E-H': 1, '1ES': 1, '1ES-H': 1, 'SH-H': 1, 'MH': 1,
    'RH': 2, 'RH-H': 2,
    'ERH': 3,
    'BRH-PB': 4, 'BRH-FB': 4, 'BRH-QB': 4, 'BRH-LB': 4, 'BRH-DB': 4, 'BRH-R': 4, 'TRH': 4,
    'RH-MB': 5,
    'EX': 6, 'GX': 6, 'V': 6, 'VX': 6, 'VST': 6, 'UR': 6,
    'GS': 7, 'SHN': 7, 'LGD': 7, 'BRK': 7,
    'IR': 8, 'SIR': 8, 'HR': 8, 'DR': 8, 'AS': 8,
}

# Check if variant_sort column exists
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='products_pokemonproduct' AND column_name='variant_sort'
    """)
    exists = cursor.fetchone()

if not exists:
    print("Adding variant_sort column...")
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE products_pokemonproduct ADD COLUMN variant_sort INTEGER DEFAULT 9")
    print("Column added")
else:
    print("Column already exists")

# Update values
print("Updating variant_sort values...")
with connection.cursor() as cursor:
    for variant, sort_val in VARIANT_ORDER.items():
        cursor.execute(
            "UPDATE products_pokemonproduct SET variant_sort = %s WHERE variant_override = %s",
            [sort_val, variant]
        )
        count = cursor.rowcount
        if count > 0:
            print(f"  {variant}: {count} records set to {sort_val}")

print("Done!")
