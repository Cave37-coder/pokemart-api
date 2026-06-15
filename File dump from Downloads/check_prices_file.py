import json

with open("tcgcsv_prices_full.json") as f:
    raw = json.load(f)

print(f"Total keys in tcgcsv_prices_full.json: {len(raw)}")
print("Sample keys:")
for k, v in list(raw.items())[:10]:
    print(f"  {repr(k)} = {v}")
