import psycopg2

local = psycopg2.connect(host='127.0.0.1', dbname='pokemart', user='postgres', password='pokemart123')
railway = psycopg2.connect('postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway')

local_cur = local.cursor()
railway_cur = railway.cursor()

local_cur.execute("SELECT pb_id, stock FROM products_pokemonproduct WHERE stock > 0")
rows = local_cur.fetchall()
print(f'Found {len(rows)} cards with stock')

updated = 0
for pb_id, stock in rows:
    railway_cur.execute('UPDATE products_pokemonproduct SET stock = %s WHERE pb_id = %s', (stock, pb_id))
    updated += railway_cur.rowcount

railway.commit()
print(f'Updated {updated} rows on Railway')
local.close()
railway.close()
