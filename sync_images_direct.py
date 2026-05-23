import psycopg2

# Connect to local
local = psycopg2.connect(host='127.0.0.1', dbname='pokemart', user='postgres', password='pokemart123')
railway = psycopg2.connect('postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway')

local_cur = local.cursor()
railway_cur = railway.cursor()

print('Fetching image_urls from local...')
local_cur.execute("SELECT pb_id, image_url FROM products_pokemonproduct WHERE image_url IS NOT NULL AND image_url != ''")
rows = local_cur.fetchall()
print(f'Got {len(rows)} rows with images')

print('Updating Railway...')
updated = 0
for pb_id, image_url in rows:
    railway_cur.execute('UPDATE products_pokemonproduct SET image_url = %s WHERE pb_id = %s', (image_url, pb_id))
    updated += railway_cur.rowcount

railway.commit()
print(f'Done. Updated {updated} rows on Railway')

local.close()
railway.close()
