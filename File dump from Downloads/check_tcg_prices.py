import requests

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

# Get groups, find CRI
r = requests.get(f"{TCGCSV_BASE}/groups", headers=HEADERS, timeout=30)
groups = r.json()
if isinstance(groups, dict):
    groups = groups.get("results", groups.get("data", []))

# Find a recent group (CRI = Chaos Rising)
cri = next((g for g in groups if 'Chaos' in str(g.get('name',''))), groups[0])
print("Group:", cri)

gid = cri.get("groupId") or cri.get("id")
r = requests.get(f"{TCGCSV_BASE}/{gid}/prices", headers=HEADERS, timeout=30)
prices = r.json()
if isinstance(prices, dict):
    prices = prices.get("results", prices.get("data", []))

# Show first 20 rows raw
print(f"\nFirst 20 price rows from group {gid}:")
for row in prices[:20]:
    print(row)
