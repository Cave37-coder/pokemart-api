import requests
HEADERS = {"User-Agent": "PokeBulkSA/1.0"}

# Check multiple sets to understand all possible subTypeNames
test_sets = [
    (24587, "POR Perfect Order"),
    (24541, "ASC Ascended Heroes"),
    (3020,  "BRS Trainer Gallery"),
    (22880, "Prize Pack Series"),
    (23821, "PRE Prismatic Evolutions"),
    (17689, "CRZ Galarian Gallery"),
    (604,   "Base Set"),
    (1402,  "HeartGold SoulSilver"),
]

all_subtypes = set()
for gid, name in test_sets:
    prices = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/prices", headers=HEADERS).json()
    prices = prices.get("results", prices) if isinstance(prices, dict) else prices
    prods = requests.get(f"https://tcgcsv.com/tcgplayer/3/{gid}/products", headers=HEADERS).json()
    prods = prods.get("results", prods) if isinstance(prods, dict) else prods
    cards = [p for p in prods if any(e.get("name") == "Number" for e in p.get("extendedData", []))]
    subtypes = set(p.get("subTypeName","") for p in prices)
    all_subtypes.update(subtypes)
    print(f"{name:35} cards={len(cards):4} price_rows={len(prices):4} subtypes={sorted(subtypes)}")

print(f"\nALL unique subTypeNames across sets:")
for s in sorted(all_subtypes):
    print(f"  '{s}'")
