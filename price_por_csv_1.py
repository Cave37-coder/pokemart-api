"""
Fetches POR pricing from TCGCSV and updates por_enriched.csv with ZAR prices.

Formula: USD x 1.1 x exchange_rate, rounded UP to nearest R0.50

Run from project root:
    cd C:\\Users\\texca\\pokemart-api
    python price_por_csv.py

Input:  por_enriched.csv
Output: por_final.csv
"""

import re, math, requests, os
import pandas as pd

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
POKEMON_CAT = 3
MARKUP      = 1.1
ROUND_TO    = 0.50
MIN_PRICE   = 1.0
INPUT_FILE  = "por_enriched.csv"
OUTPUT_FILE = "por_final.csv"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "PokeBulkSA/1.0", "Accept": "application/json"})


def round_up_to(value, nearest):
    return math.ceil(value / nearest) * nearest


def zar_price(usd, rate):
    if not usd or usd <= 0:
        return None
    return max(round_up_to(usd * rate * MARKUP, ROUND_TO), MIN_PRICE)


def get_json(url, verify=True):
    try:
        r = SESSION.get(url, timeout=30, verify=verify)
        if r.status_code == 200:
            return r.json()
        print(f"  HTTP {r.status_code} for {url}")
    except requests.exceptions.SSLError:
        if verify:
            print(f"  SSL error, retrying without verification...")
            return get_json(url, verify=False)
        print(f"  SSL error (unverified) for {url}")
    except Exception as e:
        print(f"  Error: {e}")
    return None


# ── Exchange rate ─────────────────────────────────────────────────────────────
print("Fetching USD/ZAR exchange rate...")
rate = 18.50
for url in ["https://api.exchangerate-api.com/v4/latest/USD",
            "https://open.er-api.com/v6/latest/USD"]:
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json()
            r2 = d.get("rates", {}).get("ZAR") or d.get("conversion_rates", {}).get("ZAR")
            if r2:
                rate = r2
                print(f"  1 USD = R{rate:.2f}")
                break
    except Exception:
        continue
else:
    print(f"  Using fallback rate R{rate:.2f}")

# ── Find POR group ────────────────────────────────────────────────────────────
print("\nSearching TCGCSV for Perfect Order...")
por_group = None

data = get_json(f"{TCGCSV_BASE}/{POKEMON_CAT}/groups")
if not data:
    print("ERROR: Cannot reach TCGCSV.")
    print("Open this in your browser to check: https://tcgcsv.com/tcgplayer/3/groups")
    exit(1)

all_results = data.get("results", [])
total = data.get("totalItems", len(all_results))

# If paginated, fetch remaining pages
offset = len(all_results)
while offset < total:
    more = get_json(f"{TCGCSV_BASE}/{POKEMON_CAT}/groups?offset={offset}&limit=100")
    if not more or not more.get("results"):
        break
    all_results.extend(more["results"])
    offset += len(more["results"])

print(f"  Total groups fetched: {len(all_results)}")

for g in all_results:
    name = g.get("name", "").lower()
    abbr = g.get("abbreviation", "").upper()
    if "perfect order" in name or abbr in ("ME3", "ME03"):
        por_group = g
        break

if not por_group:
    print("\nCould not find Perfect Order. MEG-era groups found:")
    for g in all_results:
        abbr = g.get("abbreviation", "").upper()
        name = g.get("name", "")
        if "mega" in name.lower() or abbr.startswith("ME"):
            print(f"  groupId={g['groupId']:6d} | abbr={abbr:8s} | {name}")
    print("\nIf you see it above with a different abbreviation, hardcode:")
    print("  por_group = {'groupId': XXXXX, 'name': 'Perfect Order', 'abbreviation': 'ME3'}")
    exit(1)

group_id = por_group["groupId"]
print(f"  Found: {por_group['name']} (groupId={group_id})")

# ── Fetch products ────────────────────────────────────────────────────────────
print(f"\nFetching products...")
prod_data = get_json(f"{TCGCSV_BASE}/{POKEMON_CAT}/{group_id}/products")
if not prod_data:
    print("ERROR: Could not fetch products")
    exit(1)

prod_num = {}
for p in prod_data.get("results", []):
    pid = p["productId"]
    for ext in p.get("extendedData", []):
        if ext["name"] == "Number":
            num = ext["value"].split("/")[0].lstrip("0") or "0"
            prod_num[pid] = num
            break
print(f"  {len(prod_num)} products mapped")

# ── Fetch prices ──────────────────────────────────────────────────────────────
print(f"\nFetching prices...")
price_data = get_json(f"{TCGCSV_BASE}/{POKEMON_CAT}/{group_id}/prices")
if not price_data:
    print("ERROR: Could not fetch prices")
    exit(1)

price_lookup = {}
for row in price_data.get("results", []):
    pid     = row.get("productId")
    subtype = (row.get("subTypeName") or "").lower()
    market  = row.get("marketPrice")
    if pid in prod_num and market:
        price_lookup[(prod_num[pid], subtype)] = float(market)

print(f"  {len(price_lookup)} price entries")
print("  Sample prices:")
for (num, sub), usd in list(price_lookup.items())[:6]:
    print(f"    Card {num:>4} | {sub:20s} | ${usd:.2f} → R{zar_price(usd, rate):.2f}")

# ── Update CSV ────────────────────────────────────────────────────────────────
VARIANT_MAP = {
    "Normal":       "normal",
    "Holofoil":     "holofoil",
    "Reverse Holo": "reverse holofoil",
}

if not os.path.exists(INPUT_FILE):
    print(f"\nERROR: {INPUT_FILE} not found. Run enrich_por_csv.py first.")
    exit(1)

df = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False)
print(f"\nLoaded {len(df)} rows from {INPUT_FILE}")

matched, no_price = 0, []

for idx, row in df.iterrows():
    m = re.match(r'me3-(\d+)-', row["sku"])
    if not m:
        continue
    num     = str(int(m.group(1)))
    subtype = VARIANT_MAP.get(row["option:Variant"], "normal")

    usd = price_lookup.get((num, subtype))
    if usd is None:
        for fb in ["normal", "reverse holofoil", "holofoil"]:
            usd = price_lookup.get((num, fb))
            if usd:
                break

    if usd:
        df.at[idx, "price"] = str(zar_price(usd, rate))
        matched += 1
    else:
        no_price.append(f"{row['sku']} ({row['option:Variant']})")

df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print()
print("-" * 50)
print(f"  Prices set : {matched}/{len(df)}")
if no_price:
    print(f"  No price   : {len(no_price)}")
    for p in no_price[:10]:
        print(f"    {p}")
    if len(no_price) > 10:
        print(f"    ... +{len(no_price)-10} more")
print(f"  Output     : {OUTPUT_FILE}")
print("-" * 50)

print("\nSample output:")
priced = df[df['price'].apply(lambda x: float(x) > 1.0 if x else False)]
for _, row in priced.head(10).iterrows():
    print(f"  {row['sku']:25s} | {row['option:Variant']:15s} | R{row['price']}")
