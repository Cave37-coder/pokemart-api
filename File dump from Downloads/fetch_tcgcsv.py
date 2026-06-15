import requests, json, time, os

HEADERS = {"User-Agent": "PokeBulkSA/1.0"}
BASE = "https://tcgcsv.com/tcgplayer/3"

print("Fetching groups...")
groups = requests.get(f"{BASE}/groups", headers=HEADERS, timeout=30).json()
if isinstance(groups, dict):
    groups = groups.get("results", groups.get("data", groups))
print(f"  {len(groups)} groups found")

# Save groups
with open("tcgcsv_groups.json", "w") as f:
    json.dump(groups, f, indent=2)
print("  Saved tcgcsv_groups.json")

# Fetch all products for every group
all_products = {}
for i, g in enumerate(sorted(groups, key=lambda x: x.get("groupId", 0))):
    gid = g.get("groupId") or g.get("id")
    name = g.get("name", "?")
    abbr = g.get("abbreviation", "?")
    try:
        prods = requests.get(f"{BASE}/{gid}/products", headers=HEADERS, timeout=30).json()
        if isinstance(prods, dict):
            prods = prods.get("results", prods.get("data", prods))
        # Only keep cards (have Number in extendedData)
        cards = []
        for p in (prods if isinstance(prods, list) else []):
            ext = {e["name"]: e["value"] for e in p.get("extendedData", [])}
            if "Number" in ext:
                p["_number"] = ext["Number"]
                p["_rarity"] = ext.get("Rarity", "")
                cards.append(p)
        all_products[gid] = {
            "groupId": gid,
            "name": name,
            "abbreviation": abbr,
            "cards": cards
        }
        print(f"  [{i+1}/{len(groups)}] gid={gid:6} {abbr:20} {name:40} cards={len(cards)}")
        time.sleep(0.2)
    except Exception as e:
        print(f"  [{i+1}/{len(groups)}] gid={gid:6} FAILED: {e}")
        all_products[gid] = {"groupId": gid, "name": name, "abbreviation": abbr, "cards": [], "error": str(e)}

with open("tcgcsv_all_products.json", "w") as f:
    json.dump(all_products, f, indent=2)

total_cards = sum(len(v["cards"]) for v in all_products.values())
print(f"\nDone. Total card products: {total_cards}")
print("Saved tcgcsv_all_products.json")
