import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

import requests
HEADERS = {"User-Agent": "PokeBulkSA/1.0"}

# Fetch ASC group from TCGCSV
groups = requests.get("https://tcgcsv.com/tcgplayer/3/groups", headers=HEADERS).json()
groups = groups.get("results", groups) if isinstance(groups, dict) else groups

# Find Ascended Heroes
asc = next((g for g in groups if "Ascended" in g.get("name","")), None)
if asc:
    gid = asc.get("groupId") or asc.get("id")
    print(f"Found: {asc.get('name')} gid={gid}")
    
    # Get prices
    prices = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/prices", headers=HEADERS).json()
    prices = prices.get("results", prices) if isinstance(prices, dict) else prices
    
    # Show unique subTypeNames
    subtypes = set(p.get("subTypeName","") for p in prices)
    print(f"SubTypeNames: {sorted(subtypes)}")
    
    # Show ball variant examples
    ball_prices = [p for p in prices if p.get("subTypeName","") and "ball" in p.get("subTypeName","").lower()]
    for p in ball_prices[:10]:
        print(f"  {p.get('subTypeName')} - market={p.get('marketPrice')} productId={p.get('productId')}")
else:
    print("ASC not found")
    print("Available:", [g.get("name") for g in groups[:10]])
