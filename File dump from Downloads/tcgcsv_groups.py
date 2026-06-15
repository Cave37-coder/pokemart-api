import requests, json
HEADERS = {"User-Agent": "PokeBulkSA/1.0"}

r = requests.get("https://tcgcsv.com/tcgplayer/3/groups", headers=HEADERS)
groups = r.json()
groups = groups.get("results", groups) if isinstance(groups, dict) else groups
print(f"Total groups: {len(groups)}")
print()
for g in sorted(groups, key=lambda x: x.get("groupId",0)):
    print(f"  {g.get('groupId'):6} | {g.get('abbreviation','?'):15} | {g.get('name','?')}")
