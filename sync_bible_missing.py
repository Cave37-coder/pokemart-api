"""
sync_bible_to_railway.py
Syncs missing records from Bible CSV directly to Railway via psycopg2.
Bypasses Django for speed. Only inserts records not already in Railway.
Run: python sync_bible_to_railway.py
"""
import psycopg2
import psycopg2.extras
import csv
import os
import sys

RAILWAY_DB = "postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway"

# Find Bible CSV
BIBLE_PATHS = [
    "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv",
    r"C:\Users\texca\pokemart-api\pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv",
]
BIBLE = None
for p in BIBLE_PATHS:
    if os.path.exists(p):
        BIBLE = p
        break
if not BIBLE:
    print("ERROR: Bible CSV not found")
    sys.exit(1)

print(f"Using Bible CSV: {BIBLE}")

print("Connecting to Railway...")
conn = psycopg2.connect(RAILWAY_DB)
cur = conn.cursor()

# Get existing pb_ids on Railway
print("Fetching existing pb_ids from Railway...")
cur.execute("SELECT pb_id FROM products_pokemonproduct")
existing = set(row[0] for row in cur.fetchall())
print(f"Railway has {len(existing)} records")

# Get set code -> ID mapping from Railway
cur.execute("SELECT code, id FROM products_cardset")
set_map = {row[0]: row[1] for row in cur.fetchall()}

# Get category ID
cur.execute("SELECT id FROM products_category WHERE slug='cards' LIMIT 1")
row = cur.fetchone()
if not row:
    cur.execute("SELECT id FROM products_category LIMIT 1")
    row = cur.fetchone()
cat_id = row[0] if row else 1

from datetime import datetime, timezone
NOW = datetime.now(timezone.utc)

def s(v):
    return v if v is not None else ''

def num(v):
    try:
        return int(v) if v and v.strip() else None
    except:
        return None

def dec(v):
    try:
        return float(v) if v and v.strip() else None
    except:
        return None

BATCH_SIZE = 500
rows = []
skipped = 0
inserted = 0
errors = 0
total_read = 0

print("Reading Bible CSV...")
with open(BIBLE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    print(f"CSV columns: {len(fieldnames)}")

    for row in reader:
        total_read += 1
        pb_id = row.get('pb_id', '').strip()
        if not pb_id or pb_id in existing:
            skipped += 1
            continue

        set_code = row.get('set_code', '').strip()
        railway_set_id = set_map.get(set_code)
        if not railway_set_id:
            skipped += 1
            continue

        name = s(row.get('name', ''))
        if not name:
            skipped += 1
            continue

        # variant_sort: N=0, H=1, RH=2, 1E=3
        vmap = {'N': 0, 'H': 1, 'RH': 2, '1E': 3, 'PB': 4, 'MB': 5}
        variant_sort_str = row.get('variant_sort', 'N').strip()
        variant_sort = vmap.get(variant_sort_str, 0)

        # variant_override for Railway old schema
        vomap = {0: 'N', 1: 'H', 2: 'RH', 3: '1E', 4: 'PB', 5: 'MB'}
        variant_override = vomap.get(variant_sort, 'N')

        desc = s(row.get('description', '')) or s(row.get('flavour_text', '')) or name
        price = dec(row.get('price', '')) or 0

        rows.append((
            pb_id,
            name,
            desc,
            s(row.get('rarity', '')),
            price,
            0,  # stock
            True,  # is_active
            NOW, NOW,
            '',  # gengar_id
            pb_id,  # sku
            s(row.get('tcgplayer_id', '')),  # tcgplayer_id
            variant_override,
            s(row.get('flavour_text', '')),
            s(row.get('image_url', '')),
            s(row.get('artist', '')),
            s(row.get('attack_1_damage', '')),
            s(row.get('attack_1_name', '')),
            s(row.get('attack_1_text', '')),
            s(row.get('attack_2_damage', '')),
            s(row.get('attack_2_name', '')),
            s(row.get('attack_2_text', '')),
            s(row.get('image_small_url', '')),
            s(row.get('resistance_type', '')),
            s(row.get('resistance_value', '')),
            s(row.get('card_subtypes', '')),
            s(row.get('supertype', '')),
            s(row.get('weakness_type', '')),
            s(row.get('weakness_value', '')),
            s(row.get('ability_name', '')),
            s(row.get('ability_text', '')),
            s(row.get('ability_type', '')),
            s(row.get('name_japanese', '')),
            s(row.get('csv_sku', '')),
            num(row.get('tcgcsv_product_id', '')),
            railway_set_id,
            cat_id,
            num(row.get('card_number', '')),
            num(row.get('pokedex_number', '')),
            num(row.get('hp', '')),
            dec(row.get('price_first_edition', '')),
            dec(row.get('price_holo', '')),
            dec(row.get('price_normal', '')),
            dec(row.get('price_reverse_holo', '')),
            num(row.get('retreat_cost', '')),
            variant_sort,
            True, True, True,  # legal fields
        ))

        if len(rows) >= BATCH_SIZE:
            try:
                psycopg2.extras.execute_values(cur, """
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
                conn.commit()
                inserted += len(rows)
                print(f"  Inserted {inserted} so far (read {total_read}, skipped {skipped})")
            except Exception as e:
                conn.rollback()
                errors += 1
                print(f"  Batch error: {e}")
            rows = []

# Final batch
if rows:
    try:
        psycopg2.extras.execute_values(cur, """
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
        conn.commit()
        inserted += len(rows)
    except Exception as e:
        conn.rollback()
        errors += 1
        print(f"  Final batch error: {e}")

print()
print("=" * 60)
print(f"CSV rows read:  {total_read}")
print(f"Already exists: {skipped}")
print(f"Inserted:       {inserted}")
print(f"Errors:         {errors}")

cur.execute("SELECT COUNT(*) FROM products_pokemonproduct")
print(f"Railway total:  {cur.fetchone()[0]}")

conn.close()
