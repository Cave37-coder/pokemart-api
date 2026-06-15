import json

with open("tcgcsv_prices_full.json") as f:
    prices = json.load(f)

# Find all POP5 Ho-Oh related prices
# pid 86123 is Ho-Oh POP5
target_pid = "86123"
print(f"Prices for productId {target_pid}:")
for key, price in prices.items():
    if key.startswith(target_pid + "|"):
        print(f"  {key} = ${price}")

print()
print("Nearby productIds (86120-86130):")
for key, price in sorted(prices.items()):
    pid = key.split("|")[0]
    if 86120 <= int(pid) <= 86130:
        print(f"  {key} = ${price}")
