"""
sync_to_railway.py
Syncs missing PokemonProduct records from local DB to Railway.
Maps local (new schema) fields to Railway (old schema) columns.
Run: python sync_to_railway.py
"""
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

LOCAL_DB = "dbname=pokemart user=postgres password=pokemart123 host=127.0.0.1 port=5432"
RAILWAY_DB = "postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway"

NOW = datetime.now(timezone.utc)

print("Connecting to local DB...")
local = psycopg2.connect(LOCAL_DB)
local_cur = local.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print("Connecting to Railway DB...")
railway = psycopg2.connect(RAILWAY_DB)
railway_cur = railway.cursor()

print("Fetching existing Railway IDs...")
railway_cur.execute("SELECT tcgcsv_product_id FROM products_pokemonproduct WHERE tcgcsv_product_id IS NOT NULL")
existing_tcgcsv = set(row[0] for row in railway_cur.fetchall())
print(f"  Railway has {len(existing_tcgcsv)} records with tcgcsv_product_id")

railway_cur.execute("SELECT pb_id FROM products_pokemonproduct")
existing_pbids = set(row[0] for row in railway_cur.fetchall())
print(f"  Railway has {len(existing_pbids)} total records (by pb_id)")

print("Fetching local records...")
local_cur.execute("""
    SELECT
        p.pb_id, p.name, p.csv_sku, p.tcgcsv_product_id,
        p.card_set_id, p.category_id, p.rarity, p.artist,
        p.hp, p.image_url, p.image_small_url, p.price, p.stock,
        p.card_number, p.pokedex_number, p.variant_sort,
        p.is_active, p.legal_standard, p.legal_expanded, p.legal_unlimited,
        p.price_normal, p.price_holo, p.price_reverse_holo,
        p.price_first_edition, p.supertype, p.card_subtypes,
        p.weakness_type, p.weakness_value, p.resistance_type, p.resistance_value,
        p.retreat_cost, p.ability_name, p.ability_type, p.ability_text,
        p.attack_1_name, p.attack_1_damage, p.attack_1_text,
        p.attack_2_name, p.attack_2_damage, p.attack_2_text,
        p.description, p.flavour_text, p.name_japanese
    FROM products_pokemonproduct p
    WHERE p.tcgcsv_product_id IS NOT NULL
""")
all_local = local_cur.fetchall()
print(f"  Local has {len(all_local)} records with tcgcsv_product_id")

missing = [r for r in all_local
           if r['tcgcsv_product_id'] not in existing_tcgcsv
           and r['pb_id'] not in existing_pbids]
print(f"  Missing from Railway: {len(missing)}")

if not missing:
    print("Nothing to sync!")
    local.close()
    railway.close()
    exit()

print("Building set mappings...")
local_cur.execute("SELECT id, code FROM products_cardset")
local_sets = {row['id']: row['code'] for row in local_cur.fetchall()}

railway_cur.execute("SELECT id, code FROM products_cardset")
railway_sets = {row[1]: row[0] for row in railway_cur.fetchall()}

railway_cur.execute("SELECT id FROM products_category LIMIT 1")
railway_category_id = railway_cur.fetchone()[0]

VMAP = {0: 'N', 1: 'H', 2: 'RH', 3: '1E', 4: 'PB', 5: 'MB', 6: 'RH-H'}

def s(val):
    return val if val is not None else ''

BATCH_SIZE = 500
inserted = 0
skipped = 0
errors = 0

for i in range(0, len(missing), BATCH_SIZE):
    batch = missing[i:i+BATCH_SIZE]
    rows = []

    for r in batch:
        set_code = local_sets.get(r['card_set_id'])
        railway_set_id = railway_sets.get(set_code) if set_code else None
        if not railway_set_id:
            skipped += 1
            continue

        vsort = r['variant_sort'] if r['variant_sort'] is not None else 0
        variant_override = VMAP.get(vsort, 'N')
        desc = s(r['description']) or s(r['flavour_text']) or s(r['name'])

        rows.append((
            s(r['pb_id']), s(r['name']), desc, s(r['rarity']),
            r['price'] or 0, 0,
            r['is_active'] if r['is_active'] is not None else True,
            NOW, NOW,
            '', s(r['pb_id']), '', variant_override,
            s(r['flavour_text']), s(r['image_url']), s(r['artist']),
            s(r['attack_1_damage']), s(r['attack_1_name']), s(r['attack_1_text']),
            s(r['attack_2_damage']), s(r['attack_2_name']), s(r['attack_2_text']),
            s(r['image_small_url']),
            s(r['resistance_type']), s(r['resistance_value']),
            s(r['card_subtypes']), s(r['supertype']),
            s(r['weakness_type']), s(r['weakness_value']),
            s(r['ability_name']), s(r['ability_text']), s(r['ability_type']),
            s(r['name_japanese']), s(r['csv_sku']),
            r['tcgcsv_product_id'], railway_set_id, railway_category_id,
            r['card_number'], r['pokedex_number'], r['hp'],
            r['price_first_edition'], r['price_holo'],
            r['price_normal'], r['price_reverse_holo'],
            r['retreat_cost'], vsort,
            r['legal_standard'], r['legal_expanded'], r['legal_unlimited'],
        ))

    if not rows:
        continue

    try:
        psycopg2.extras.execute_values(railway_cur, """
            INSERT INTO products_pokemonproduct
            (pb_id, name, description, rarity, price, stock,
             is_active, created_at, updated_at,
             gengar_id, sku, tcgplayer_id, variant_override,
             flavour_text, image_url, artist,
             attack_1_damage, attack_1_name, attack_1_text,
             attack_2_damage, attack_2_name, attack_2_text,
             image_small_url, resistance_type, resistance_value,
             card_subtypes, supertype, weakness_type, weakness_value,
             ability_name, ability_text, ability_type,
             name_japanese, csv_sku,
             tcgcsv_product_id, card_set_id, category_id,
             card_number, pokedex_number, hp,
             price_first_edition, price_holo, price_normal,
             price_reverse_holo, retreat_cost, variant_sort,
             legal_standard, legal_expanded, legal_unlimited)
            VALUES %s
            ON CONFLICT (pb_id) DO NOTHING
        """, rows)
        railway.commit()
        inserted += len(rows)
        print(f"  Batch {i//BATCH_SIZE + 1}: {inserted} inserted so far")
    except Exception as e:
        railway.rollback()
        errors += 1
        print(f"  Batch {i//BATCH_SIZE + 1} error: {e}")

print()
print("=" * 60)
print(f"Inserted: {inserted}")
print(f"Skipped (no set match): {skipped}")
print(f"Errors: {errors}")

local.close()
railway.close()
