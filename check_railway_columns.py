"""
check_railway_columns.py
Checks which columns in Railway's products_pokemonproduct are NOT NULL with no default.
"""
import psycopg2

RAILWAY_DB = "postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway"

railway = psycopg2.connect(RAILWAY_DB)
cur = railway.cursor()

cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'products_pokemonproduct'
    ORDER BY ordinal_position
""")

print(f"{'COLUMN':<40} {'TYPE':<20} {'NULLABLE':<10} {'DEFAULT'}")
print("-" * 100)
for row in cur.fetchall():
    col, dtype, nullable, default = row
    marker = " <-- NOT NULL, no default" if nullable == 'NO' and default is None else ""
    print(f"{col:<40} {dtype:<20} {nullable:<10} {str(default):<30}{marker}")

railway.close()
