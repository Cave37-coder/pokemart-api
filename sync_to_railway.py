"""
Sync missing PokemonProduct records from local DB to Railway.
Run: python sync_to_railway.py
Reads from local DB, inserts missing records to Railway in bulk.
"""
import psycopg2
import psycopg2.extras
import os

LOCAL_DB = "dbname=pokemart user=postgres password=pokemart123 host=127.0.0.1 port=5432"
RAILWAY_DB = "postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway"

print("Connecting to local DB...")
local = psycopg2.connect(LOCAL_DB)
local_cur = local.cursor()

print("Connecting to Railway DB...")
railway = psycopg2.connect(RAILWAY_DB)
railway_cur = railway.cursor()

# Get all tcgcsv_product_ids already in Railway
print("Fetching existing Railway IDs...")
railway_cur.execute("SELECT tcgcsv_product_id FROM products_pokemonproduct WHERE tcgcsv_product_id IS NOT NULL")
existing_ids = set(row[0] for row in railway_cur.fetchall())
print(f"Railway has {len(existing_ids)} records with tcgcsv_id")

# Get all csv_skus already in Railway (for records without tcgcsv_id)
railway_cur.execute("SELECT csv_sku FROM products_pokemonproduct WHERE tcgcsv_product_id IS NULL AND csv_sku != ''")
existing_skus = set(row[0] for row in railway_cur.fetchall())
print(f"Railway has {len(existing_skus)} records with csv_sku only")

# Get missing records from local DB
print("Fetching missing records from local DB...")
local_cur.execute("""
    SELECT 
        p.pb_id, p.name, p.csv_sku, p.tcgcsv_product_id,
        p.card_set_id, p.category_id, p.rarity, p.artist,
        p.hp, p.image_url, p.price, p.stock,
        p.card_number, p.pokedex_number, p.variant_sort,
        p.is_active, p.legal_standard, p.legal_expanded, p.legal_unlimited,
        p.price_normal, p.price_holo, p.price_reverse_holo,
        p.price_first_edition
    FROM products_pokemonproduct p
    WHERE p.tcgcsv_product_id IS NOT NULL
""")

all_local = local_cur.fetchall()
print(f"Local DB has {len(all_local)} records with tcgcsv_id")

# Filter to only missing ones
missing = [r for r in all_local if r[3] not in existing_ids]
print(f"Missing from Railway: {len(missing)}")

if not missing:
    print("Nothing to sync!")
    exit()

# Get Railway card_set mapping (local set IDs may differ from Railway)
print("Building set code mapping...")
local_cur.execute("SELECT id, code FROM products_cardset")
local_sets = {row[0]: row[1] for row in local_cur.fetchall()}

railway_cur.execute("SELECT id, code FROM products_cardset")
railway_sets = {row[1]: row[0] for row in railway_cur.fetchall()}

# Get Railway category id
railway_cur.execute("SELECT id FROM products_category WHERE slug='pokemon-card' LIMIT 1")
row = railway_cur.fetchone()
railway_category_id = row[0] if row else None

# Bulk insert in batches
BATCH_SIZE = 500
inserted = 0
errors = 0

for i in range(0, len(missing), BATCH_SIZE):
    batch = missing[i:i+BATCH_SIZE]
    rows = []
    
    for r in batch:
        pb_id, name, csv_sku, tcgcsv_id, local_set_id, cat_id, rarity, artist, \
        hp, image_url, price, stock, card_number, pokedex_number, variant_sort, \
        is_active, legal_standard, legal_expanded, legal_unlimited, \
        price_normal, price_holo, price_rh, price_1st = r
        reg_mark = ''
        
        # Map local set_id to Railway set_id
        set_code = local_sets.get(local_set_id)
        railway_set_id = railway_sets.get(set_code)
        
        if not railway_set_id:
            errors += 1
            continue
            
        rows.append((
            pb_id, name, csv_sku, tcgcsv_id,
            railway_set_id, railway_category_id, rarity, artist or '',
            hp, image_url or '', price, 0,  # stock=0
            card_number, pokedex_number, variant_sort or 'N',
            is_active, legal_standard, legal_expanded, legal_unlimited,
            price_normal, price_holo, price_rh, price_1st, reg_mark
        ))
    
    if not rows:
        continue
        
    try:
        psycopg2.extras.execute_values(railway_cur, """
            INSERT INTO products_pokemonproduct 
            (pb_id, name, csv_sku, tcgcsv_product_id,
             card_set_id, category_id, rarity, artist,
             hp, image_url, price, stock,
             card_number, pokedex_number, variant_sort,
             is_active, legal_standard, legal_expanded, legal_unlimited,
             price_normal, price_holo, price_reverse_holo,
             price_first_edition, regulation_mark)
            VALUES %s
            ON CONFLICT (pb_id) DO NOTHING
        """, rows)
        railway.commit()
        inserted += len(rows)
        print(f"  Inserted batch {i//BATCH_SIZE + 1}: {inserted} total so far")
    except Exception as e:
        railway.rollback()
        errors += 1
        print(f"  Batch error: {e}")

print(f"\nDone! Inserted: {inserted}, Errors: {errors}")
local.close()
railway.close()
