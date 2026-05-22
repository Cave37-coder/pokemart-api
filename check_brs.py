import json
with open("tcgcsv_all_products.json") as f:
    data = json.load(f)

brs = data["2948"]["cards"]
print(f"BRS cards in TCGCSV: {len(brs)}")
print()
for c in brs[:15]:
    print(f"  pid={c['productId']}  num={c['_number']}  subType={repr(c.get('subTypeName',''))}  name={c['name']}")
