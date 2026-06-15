import requests
HEADERS = {"User-Agent": "PokeBulkSA/1.0"}

# Check prices for POR - this has the card variants
gid = 24587
prices = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/prices", headers=HEADERS).json()
prices = prices.get("results", prices) if isinstance(prices, dict) else prices
print(f"POR price rows: {len(prices)}")

# Show unique subTypeNames from prices
subtypes = set(p.get("subTypeName","") for p in prices)
print(f"SubTypeNames in prices: {sorted(subtypes)}")

# Show first 15 price rows
for p in prices[:15]:
    print(f"  productId={p.get('productId')} | subType={p.get('subTypeName','?'):20} | market={p.get('marketPrice')}")

# Now check products filtered to cards only - look at extendedData
print("\n--- Products with card numbers ---")
prods = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/products", headers=HEADERS).json()
prods = prods.get("results", prods) if isinstance(prods, dict) else prods
cards_only = [p for p in prods if any(e.get("name") == "Number" for e in p.get("extendedData", []))]
print(f"Products with card numbers: {len(cards_only)} out of {len(prods)}")
for p in cards_only[:10]:
    ext = {e["name"]: e["value"] for e in p.get("extendedData", [])}
    print(f"  productId={p.get('productId')} | {p.get('name'):35} | #{ext.get('Number','?')} | rarity={ext.get('Rarity','?')}")
