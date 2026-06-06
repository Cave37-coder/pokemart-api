"""
sync_bible_tcgcsv.py — Sync missing Bible CSV cards to Railway.
Uses TCGCSV-{product_id} as pb_id. Only inserts missing records.
"""
import psycopg2, psycopg2.extras, csv, os, sys
from datetime import datetime, timezone

RAILWAY_DB = "postgresql://postgres:dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm@nozomi.proxy.rlwy.net:59678/railway"
BIBLE = "pokebulk_bible_cards_only_20260531_0803_bulba_enriched_ptcg_enriched_FINAL.csv"

if not os.path.exists(BIBLE):
    print(f"ERROR: {BIBLE} not found"); sys.exit(1)

NOW = datetime.now(timezone.utc)
VMAP = {'Normal':'N','Holofoil':'H','Reverse Holofoil':'RH','Reverse Holo':'RH',
        '1st Edition':'1E','Shadowless':'N','Poke Ball':'PB','Master Ball':'MB','':'N'}
VSORT = {'N':0,'H':1,'RH':2,'1E':3,'PB':4,'MB':5}

def s(v): return v.strip() if v else ''
def num(v):
    try: return int(str(v).strip()) if v and str(v).strip() else None
    except: return None
def dec(v):
    try: return float(str(v).strip()) if v and str(v).strip() else None
    except: return None

print("Connecting to Railway...")
conn = psycopg2.connect(RAILWAY_DB)
cur = conn.cursor()

cur.execute("SELECT pb_id FROM products_pokemonproduct")
existing = set(r[0] for r in cur.fetchall())
print(f"Railway has {len(existing)} records")

cur.execute("SELECT code, id FROM products_cardset")
set_map = {r[0]: r[1] for r in cur.fetchall()}

cur.execute("SELECT id FROM products_category LIMIT 1")
cat_id = cur.fetchone()[0]

INSERT_SQL = """
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
    VALUES %s ON CONFLICT (pb_id) DO NOTHING
"""
# 49 columns exactly

rows = []
total = skipped = inserted = errors = no_set = 0

print("Reading CSV...")
with open(BIBLE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        total += 1
        pid = s(row.get('product_id',''))
        if not pid: skipped += 1; continue
        pb_id = f"TCGCSV-{pid}"
        if pb_id in existing: skipped += 1; continue

        set_code = s(row.get('set_code',''))
        sid = set_map.get(set_code)
        if not sid: no_set += 1; skipped += 1; continue

        name = s(row.get('name',''))
        if not name: skipped += 1; continue

        vo = VMAP.get(s(row.get('variant','')), 'N')
        vs = VSORT.get(vo, 0)
        price = dec(row.get('pokebulk_zar','')) or 0
        img = s(row.get('final_image_url','')) or s(row.get('bulba_image_url',''))
        art = s(row.get('final_artist','')) or s(row.get('artist',''))
        pdx = num(row.get('final_pokedex','')) or num(row.get('bulba_pokedex_number',''))
        card_text = s(row.get('card_text',''))

        # card_number from "001/102"
        nstr = s(row.get('number',''))
        cnum = None
        if '/' in nstr:
            try: cnum = int(nstr.split('/')[0])
            except: pass

        # 49 values matching 49 columns
        rows.append((
            pb_id, name, card_text or name, s(row.get('rarity','')), price, 0,  # 6
            True, NOW, NOW,                                                        # 3
            '', f"PKB-{pid}", '', vo,                                             # 4
            card_text, img, art,                                                   # 3
            '','','',                                                              # attack_1 x3
            '','','',                                                              # attack_2 x3
            '','','',                                                              # image_small, resist x2
            s(row.get('stage','')), '', s(row.get('weakness','')),'',             # card_subtypes,supertype,weakness x2
            '','','',                                                              # ability x3
            '', '',                                                                # name_jp, csv_sku
            num(pid), sid, cat_id,                                                # tcgcsv_id, set_id, cat_id
            cnum, pdx, num(row.get('hp','')),                                     # card_num, pdx, hp
            None,                                                                  # price_first_edition
            price if vo=='H' else None,                                           # price_holo
            price if vo=='N' else None,                                           # price_normal
            price if vo=='RH' else None,                                          # price_reverse_holo
            num(row.get('retreat_cost','')), vs,                                  # retreat, variant_sort
            True, True, True,                                                      # legality x3
        ))

        if len(rows) >= 500:
            try:
                psycopg2.extras.execute_values(cur, INSERT_SQL, rows)
                conn.commit()
                inserted += len(rows)
                print(f"  {inserted} inserted (read {total})")
            except Exception as e:
                conn.rollback(); errors += 1
                print(f"  Error: {e}")
            rows = []

if rows:
    try:
        psycopg2.extras.execute_values(cur, INSERT_SQL, rows)
        conn.commit(); inserted += len(rows)
    except Exception as e:
        conn.rollback(); errors += 1; print(f"  Final error: {e}")

cur.execute("SELECT COUNT(*) FROM products_pokemonproduct")
print(f"\nDone! Inserted={inserted} Errors={errors} No_set={no_set}")
print(f"Railway total: {cur.fetchone()[0]}")
conn.close()
