import requests
HEADERS = {"User-Agent": "PokeBulkSA/1.0"}

# Check PRE (Prismatic Evolutions) and POR (Perfect Order)
for gid, name in [(23821, "PRE Prismatic Evolutions"), (24587, "POR Perfect Order")]:
    print(f"\n=== {name} (gid={gid}) ===")
    prods = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/products", headers=HEADERS).json()
    prods = prods.get("results", prods) if isinstance(prods, dict) else prods
    print(f"Total products: {len(prods)}")
    subtypes = set(p.get("subTypeName","") for p in prods)
    print(f"SubTypeNames: {sorted(subtypes)}")
    
    # Show first 10
    for p in prods[:10]:
        ext = {e["name"]: e["value"] for e in p.get("extendedData", [])}
        print(f"  {p.get('productId')} | {p.get('name'):40} | subType={p.get('subTypeName','?'):20} | #{ext.get('Number','?')}")
