import json

with open("tcgcsv_prices.json") as f:
    prices = json.load(f)

# Ho-Oh POP5 pid=86123 — what price rows exist near this ID?
target = 86123
nearby = {k: v for k, v in prices.items() if abs(int(k) - target) < 50}
for pid, price in sorted(nearby.items(), key=lambda x: int(x[0])):
    print(f"  pid={pid}  price=${price}")
