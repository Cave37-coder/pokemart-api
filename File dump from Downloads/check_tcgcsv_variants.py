import requests
HEADERS = {"User-Agent": "PokeBulkSA/1.0"}

# Check BRS Trainer Gallery - groupId 3020
for gid, name in [(3020, "BRS Trainer Gallery"), (22880, "Prize Pack Series")]:
    print(f"\n=== {name} (gid={gid}) ===")
    prods = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/products", headers=HEADERS).json()
    prods = prods.get("results", prods) if isinstance(prods, dict) else prods
    print(f"Total products: {len(prods)}")
    
    # Show first 5 products in detail
    for p in prods[:5]:
        ext = {e["name"]: e["value"] for e in p.get("extendedData", [])}
        print(f"  productId={p.get('productId')} | name={p.get('name')} | subType={p.get('subTypeName','?')} | number={ext.get('Number','?')} | rarity={ext.get('Rarity','?')}")
    
    # Show all unique subTypeNames
    subtypes = set(p.get("subTypeName","") for p in prods)
    print(f"  SubTypeNames: {sorted(subtypes)}")
