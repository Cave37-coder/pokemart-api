import requests, json, time

HEADERS = {"User-Agent": "PokeBulkSA/1.0"}
BASE = "https://tcgcsv.com/tcgplayer/3"

with open("tcgcsv_groups.json") as f:
    groups = json.load(f)

# Store as {productId_SubType: price} — e.g. "86123_Normal": 44.77, "86124_Reverse Holofoil": 30.48
all_prices = {}
total = len(groups)

for i, g in enumerate(groups, 1):
    gid = g.get("groupId") or g.get("id")
    try:
        r = requests.get(f"{BASE}/{gid}/prices", headers=HEADERS, timeout=30)
        rows = r.json()
        if isinstance(rows, dict):
            rows = rows.get("results", rows.get("data", []))
        for row in (rows if isinstance(rows, list) else []):
            pid = row.get("productId")
            subtype = row.get("subTypeName", "") or ""
            mid = row.get("midPrice") or row.get("marketPrice") or row.get("lowPrice") or 0
            if pid and mid and float(mid) > 0:
                key = f"{pid}|{subtype}"
                all_prices[key] = float(mid)
        print(f"[{i}/{total}] gid={gid} rows={len(rows) if isinstance(rows, list) else 0}")
        time.sleep(0.2)
    except Exception as e:
        print(f"[{i}/{total}] gid={gid} FAILED: {e}")

with open("tcgcsv_prices_full.json", "w") as f:
    json.dump(all_prices, f)

print(f"\nDone. {len(all_prices)} price rows saved to tcgcsv_prices_full.json")
