import json

with open("tcgcsv_all_products.json") as f:
    data = json.load(f)

# POP5 = gid 1439
pop5 = data["1439"]["cards"]
print(f"POP5 TCGCSV cards: {len(pop5)}")
for c in pop5[:10]:
    print(f"  pid={c['productId']}  num={c['_number']}  subType={repr(c.get('subTypeName',''))}  name={c['name']}")
