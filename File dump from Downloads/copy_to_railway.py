import psycopg2
import psycopg2.extras

LOCAL = dict(host='127.0.0.1', dbname='pokemart', user='postgres', password='pokemart123')
RAILWAY = 'postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway'
BATCH = 200

local = psycopg2.connect(**LOCAL)
railway = psycopg2.connect(RAILWAY)
lc = local.cursor(cursor_factory=psycopg2.extras.DictCursor)
rc = railway.cursor()

rc.execute("SELECT pb_id FROM products_pokemonproduct")
existing = set(row[0] for row in rc.fetchall())
print(f"Existing on Railway: {len(existing)}")

rc.execute("SELECT id, code FROM products_era")
rw_eras = {row[1]: row[0] for row in rc.fetchall()}
default_era_id = list(rw_eras.values())[0]

rc.execute("SELECT id, code FROM products_cardset")
rw_sets = {row[1]: row[0] for row in rc.fetchall()}

rc.execute("SELECT id, name FROM products_category")
rw_cats = {row[1]: row[0] for row in rc.fetchall()}

lc.execute("SELECT id, code FROM products_era")
local_eras = {row[0]: row[1] for row in lc.fetchall()}

lc.execute("SELECT id, code, era_id, name, logo_url, symbol_url, release_date FROM products_cardset")
local_sets = {}
for row in lc.fetchall():
    local_sets[row[0]] = {
        'code': row[1], 'era_id': row[2], 'name': row[3],
        'logo_url': row[4] or '', 'symbol_url': row[5] or '', 'release_date': row[6],
    }

lc.execute("SELECT id, name FROM products_category")
local_cats = {row[0]: row[1] for row in lc.fetchall()}

CARDSET_SQL = "INSERT INTO products_cardset (code, name, era_id, logo_url, symbol_url, release_date, total_cards) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name RETURNING id"
CATEGORY_SQL = "INSERT INTO products_category (name) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id"

def get_or_create_cardset(local_set_id):
    if not local_set_id or local_set_id not in local_sets:
        return None
    s = local_sets[local_set_id]
    code = s['code']
    if code in rw_sets:
        return rw_sets[code]
    era_code = local_eras.get(s['era_id'], 'B1')
    era_id = rw_eras.get(era_code, default_era_id)
    rc.execute(CARDSET_SQL, (code, s['name'], era_id, s['logo_url'], s['symbol_url'], s['release_date'], 0))
    new_id = rc.fetchone()[0]
    rw_sets[code] = new_id
    railway.commit()
    return new_id

def get_or_create_category(local_cat_id):
    if not local_cat_id or local_cat_id not in local_cats:
        return None
    name = local_cats[local_cat_id]
    if name in rw_cats:
        return rw_cats[name]
    rc.execute(CATEGORY_SQL, (name,))
    row = rc.fetchone()
    if row:
        rw_cats[name] = row[0]
        railway.commit()
        return row[0]
    return None

lc.execute("SELECT * FROM products_pokemonproduct ORDER BY id")

INSERT_SQL = """INSERT INTO products_pokemonproduct (
    pb_id, sku, csv_sku, tcgplayer_id, tcgcsv_product_id, gengar_id,
    name, name_japanese, description, flavour_text,
    category_id, card_set_id, rarity, pokedex_number, card_number,
    variant_override, hp, artist, supertype, card_subtypes,
    weakness_type, weakness_value, resistance_type, resistance_value,
    retreat_cost, ability_name, ability_type, ability_text,
    attack_1_name, attack_1_damage, attack_1_text,
    attack_2_name, attack_2_damage, attack_2_text,
    image_url, image_small_url, price, price_normal, price_holo,
    price_reverse_holo, price_first_edition,
    stock, is_active, created_at, updated_at
) VALUES %s ON CONFLICT (pb_id) DO NOTHING"""

batch = []
created = skipped = errors = 0
total = 0

for row in lc:
    total += 1
    if row['pb_id'] in existing:
        skipped += 1
        continue

    card_set_id = get_or_create_cardset(row['card_set_id'])
    category_id = get_or_create_category(row['category_id'])

    batch.append((
        row['pb_id'], row['sku'] or '', row['csv_sku'] or '',
        row['tcgplayer_id'] or '', row['tcgcsv_product_id'],
        row['gengar_id'] or '', row['name'], row['name_japanese'] or '',
        row['description'] or '', row['flavour_text'] or '',
        category_id, card_set_id, row['rarity'] or 'common',
        row['pokedex_number'], row['card_number'],
        row['variant_override'] or 'N', row['hp'], row['artist'] or '',
        row['supertype'] or '', row['card_subtypes'] or '',
        row['weakness_type'] or '', row['weakness_value'] or '',
        row['resistance_type'] or '', row['resistance_value'] or '',
        row['retreat_cost'], row['ability_name'] or '',
        row['ability_type'] or '', row['ability_text'] or '',
        row['attack_1_name'] or '', row['attack_1_damage'] or '',
        row['attack_1_text'] or '', row['attack_2_name'] or '',
        row['attack_2_damage'] or '', row['attack_2_text'] or '',
        row['image_url'] or '', row['image_small_url'] or '',
        row['price'] or 0,
        row['price_normal'], row['price_holo'],
        row['price_reverse_holo'], row['price_first_edition'],
        row['stock'] or 0, row['is_active'],
        row['created_at'], row['updated_at'],
    ))

    if len(batch) >= BATCH:
        try:
            psycopg2.extras.execute_values(rc, INSERT_SQL, batch)
            railway.commit()
            created += len(batch)
            print(f"  Inserted {created} / ~36000...")
        except Exception as e:
            railway.rollback()
            errors += len(batch)
            print(f"  ERROR: {e}")
        batch = []

if batch:
    try:
        psycopg2.extras.execute_values(rc, INSERT_SQL, batch)
        railway.commit()
        created += len(batch)
    except Exception as e:
        railway.rollback()
        errors += len(batch)
        print(f"  ERROR: {e}")

print(f"\nDONE total={total} created={created} skipped={skipped} errors={errors}")
local.close()
railway.close()
