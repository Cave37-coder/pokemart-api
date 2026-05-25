import requests

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

# Check a few sets
test_sets = [
    (3068,  "ASRTG"),
    (2594,  "HIFSV"),
    (17689, "CRZGG"),
    (1729,  "GENRC"),
    (1465,  "LTRRC"),
]

for gid, code in test_sets:
    r = requests.get(f"{TCGCSV_BASE}/{gid}/products", headers=HEADERS, timeout=30)
    products = r.json().get("results", [])
    
    print(f"\n{code} (group {gid}) — first 5 card numbers:")
    count = 0
    for p in products:
        ext = p.get("extendedData", [])
        number = next((i.get("value","") for i in ext if i.get("name") == "Number"), "")
        rarity = next((i.get("value","") for i in ext if i.get("name") == "Rarity"), "")
        if number:
            print(f"  {p['name'][:30]:<30} number={number} rarity={rarity}")
            count += 1
        if count >= 5:
            break
