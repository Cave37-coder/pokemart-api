import requests, json, time

HEADERS = {"User-Agent": "PokeBulkSA/1.0"}
BASE = "https://tcgcsv.com/tcgplayer/3"

with open("tcgcsv_groups.json") as f:
    groups = json.load(f)

all_prices = {}
total = len(groups)

for i, g in enumerate(groups, 1):
    gid = g.get("groupId") or g.get("id")
    try:
        r = requests.get(f"{BASE}/{gid}/prices", headers=HEADERS, timeout=30)
        prices = r.json()
        if isinstance(prices, dict):
            prices = prices.get("results", prices.get("data", []))
        # Store as productId -> best price (midPrice or marketPrice)
        for row in (prices if isinstance(prices, list) else []):
            pid = row.get("productId")
            if pid:
                mid = row.get("midPrice") or row.get("marketPrice") or row.get("lowPrice") or 0
                if mid and mid > 0:
                    all_prices[int(pid)] = float(mid)
        print(f"[{i}/{total}] gid={gid} got {len(prices) if isinstance(prices, list) else 0} price rows")
        time.sleep(0.2)
    except Exception as e:
        print(f"[{i}/{total}] gid={gid} FAILED: {e}")

with open("tcgcsv_prices.json", "w") as f:
    json.dump(all_prices, f)

print(f"\nDone. {len(all_prices)} products with prices saved to tcgcsv_prices.json")
