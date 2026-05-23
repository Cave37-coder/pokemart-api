"""
Fetches POR pricing from TCGCSV and updates por_enriched.csv with ZAR prices.

Formula: USD × 1.1 × exchange_rate, rounded UP to nearest R0.50

Run from project root:
    cd C:\\Users\\texca\\pokemart-api
    python price_por_csv.py

Input:  por_enriched.csv  (output from enrich_por_csv.py)
Output: por_final.csv
"""

import re, math, requests

# ── Config ────────────────────────────────────────────────────────────────────
TCGCSV_BASE  = "https://tcgcsv.com/tcgplayer"
POKEMON_CAT  = 3
MARKUP       = 1.1       # 10% markup over TCG market price
ROUND_TO     = 0.50      # round up to nearest R0.50
MIN_PRICE    = 1.0       # minimum price in ZAR

INPUT_FILE   = "por_enriched.csv"
OUTPUT_FILE  = "por_final.csv"

# ── Helpers ───────────────────────────────────────────────────────────────────
def round_up_to(value, nearest):
    """Round up to nearest increment e.g. R0.50"""
    return math.ceil(value / nearest) * nearest


def zar_price(usd, rate):
    """Convert USD to ZAR with markup, round up to nearest R0.50"""
    if not usd or usd <= 0:
        return None
    zar = usd * rate * MARKUP
    zar = round_up_to(zar, ROUND_TO)
    return max(zar, MIN_PRICE)


def get(url):
    """Simple GET with error handling"""
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
    return None


# ── Step 1: Get USD/ZAR exchange rate ────────────────────────────────────────
print("Fetching USD/ZAR exchange rate...")
try:
    rate_data = requests.get(
        "https://api.exchangerate-api.com/v4/latest/USD", timeout=10
    ).json()
    rate = rate_data["rates"]["ZAR"]
    print(f"  Rate: 1 USD = R{rate:.2f}")
except Exception:
    rate = 18.50  # fallback
    print(f"  Could not fetch rate, using fallback: R{rate:.2f}")

# ── Step 2: Find POR group ID on TCGCSV ──────────────────────────────────────
print("\nFetching TCGCSV groups...")
groups_data = get(f"{TCGCSV_BASE}/{POKEMON_CAT}/groups")
if not groups_data:
    print("ERROR: Could not fetch groups from TCGCSV")
    exit(1)

# Find Perfect Order group
por_group = None
for g in groups_data.get("results", []):
    name = g.get("name", "").lower()
    abbr = g.get("abbreviation", "").lower()
    if "perfect order" in name or abbr == "me03" or abbr == "me3":
        por_group = g
        break

if not por_group:
    # Show available MEG era groups to help debug
    meg_groups = [
        g for g in groups_data.get("results", [])
        if "mega" in g.get("name", "").lower() or
           g.get("abbreviation", "").lower().startswith("me")
    ]
    print("Could not find Perfect Order group. MEG-era groups found:")
    for g in meg_groups:
        print(f"  {g.get('groupId')} | {g.get('abbreviation')} | {g.get('name')}")
    exit(1)

group_id = por_group["groupId"]
print(f"  Found: {por_group['name']} (groupId={group_id}, abbr={por_group.get('abbreviation')})")

# ── Step 3: Fetch products and prices ─────────────────────────────────────────
print(f"\nFetching products for group {group_id}...")
products_data = get(f"{TCGCSV_BASE}/{POKEMON_CAT}/{group_id}/products")
if not products_data:
    print("ERROR: Could not fetch products")
    exit(1)

print(f"\nFetching prices for group {group_id}...")
prices_data = get(f"{TCGCSV_BASE}/{POKEMON_CAT}/{group_id}/prices")
if not prices_data:
    print("ERROR: Could not fetch prices")
    exit(1)

# ── Step 4: Build lookup: (card_number, subtype) → marketPrice USD ────────────
# First build productId → card_number map
prod_num = {}
for p in products_data.get("results", []):
    pid = p["productId"]
    for ext in p.get("extendedData", []):
        if ext["name"] == "Number":
            raw = ext["value"]  # e.g. "001/088" or "88"
            # Extract just the number before the slash
            num = raw.split("/")[0].lstrip("0") or "0"
            prod_num[pid] = num
            break

# Build price lookup: (card_number_str, subtype_lower) → marketPrice
price_lookup = {}
for row in prices_data.get("results", []):
    pid     = row.get("productId")
    subtype = (row.get("subTypeName") or "").lower()  # "normal", "holofoil", "reverse holofoil"
    market  = row.get("marketPrice")

    if pid in prod_num and market:
        num = prod_num[pid]
        price_lookup[(num, subtype)] = float(market)

print(f"  Products mapped: {len(prod_num)}")
print(f"  Price entries:   {len(price_lookup)}")

# Show sample
sample = list(price_lookup.items())[:5]
for k, v in sample:
    print(f"  Card {k[0]} {k[1]}: ${v:.2f}")

# ── Step 5: Map CSV variants to TCGCSV subtypes ────────────────────────────────
VARIANT_TO_SUBTYPE = {
    "Normal":       "normal",
    "Holofoil":     "holofoil",
    "Reverse Holo": "reverse holofoil",
}


def get_price(card_num, variant, fallback_variant=None):
    """Get ZAR price for a card+variant combo"""
    subtype = VARIANT_TO_SUBTYPE.get(variant, "normal")
    usd = price_lookup.get((card_num, subtype))

    # Fallback logic
    if usd is None and fallback_variant:
        fallback_sub = VARIANT_TO_SUBTYPE.get(fallback_variant, "normal")
        usd = price_lookup.get((card_num, fallback_sub))

    if usd is None:
        # Last resort: try any price for this card
        for sub in ["normal", "reverse holofoil", "holofoil"]:
            usd = price_lookup.get((card_num, sub))
            if usd:
                break

    return zar_price(usd, rate) if usd else None


# ── Step 6: Update the CSV ─────────────────────────────────────────────────────
import pandas as pd, os

if not os.path.exists(INPUT_FILE):
    print(f"\nERROR: {INPUT_FILE} not found. Run enrich_por_csv.py first.")
    exit(1)

df = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False)
print(f"\nLoaded {len(df)} rows from {INPUT_FILE}")

matched  = 0
no_price = []

for idx, row in df.iterrows():
    # Extract card number from SKU: me3-4-norm → "4"
    m = re.match(r'me3-(\d+)-', row["sku"])
    if not m:
        continue
    card_num = str(int(m.group(1)))
    variant  = row["option:Variant"]

    price = get_price(card_num, variant)

    if price:
        df.at[idx, "price"] = str(price)
        matched += 1
    else:
        no_price.append(f"{row['sku']} ({variant})")

df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print()
print("─" * 50)
print(f"  Prices set : {matched}")
print(f"  No price   : {len(no_price)}")
if no_price:
    for p in no_price[:10]:
        print(f"    - {p}")
    if len(no_price) > 10:
        print(f"    ... +{len(no_price)-10} more")
print(f"  Output     : {OUTPUT_FILE}")
print("─" * 50)

# Show sample
print("\nSample prices:")
for _, row in df[df['price'] != '0.0'].head(8).iterrows():
    print(f"  {row['sku']:25s} {row['option:Variant']:15s} R{row['price']}")
