"""
check_tcgcsv_asc.py
Fetches ASC group from TCGCSV API and shows variant structure.
"""
import requests

# First get groups to find ASC group ID
print("Fetching TCGCSV groups...")
r = requests.get("https://tcgcsv.com/tcgplayer/groups", timeout=30)
groups = r.json()

# Find ASC group
asc_group = None
for g in groups:
    if g.get('abbreviation') == 'ASC' or 'Ascended' in g.get('name', ''):
        asc_group = g
        print(f"Found: {g}")
        break

if not asc_group:
    print("ASC not found by abbreviation, searching by name...")
    for g in groups:
        if 'ascend' in g.get('name', '').lower():
            print(f"  Possible: {g}")

if asc_group:
    gid = asc_group['groupId']
    print(f"\nFetching products for group {gid}...")
    r2 = requests.get(f"https://tcgcsv.com/tcgplayer/{gid}/products", timeout=30)
    products = r2.json()
    print(f"Total products: {len(products)}")

    # Show variant breakdown
    from collections import Counter
    variants = Counter()
    for p in products:
        for ed in p.get('extendedData', []):
            if ed.get('name') == 'Rarity':
                pass
        # Check name for variant info
        name = p.get('name', '')
        variants[name.split(' - ')[-1] if ' - ' in name else 'base'] += 1

    print("\nSample products (first 20):")
    for p in products[:20]:
        print(f"  id={p.get('productId')} | {p.get('name')} | {[e for e in p.get('extendedData',[]) if e.get('name') in ('Number','Rarity','Variant')]}")
