import json
with open("tcgcsv_db_mapping.json") as f:
    mapping = json.load(f)

target = ["MEW","CRI","ASC","PFL","MEG","MEE","LTRRC","HIFSV","SHFSV","CELCC","BRSTG","ASRTG","LORTG","SITTG","CRZGG","MCD23","MCD24","TTBB23","TTBB24","BA24"]
print("Mapped:")
for item in mapping:
    if item.get("db_code") in target:
        print(f"  {item.get('db_code'):15} group={item.get('group_id')} name={item.get('name')}")

print()
print("Not in mapping:")
mapped = [item.get("db_code") for item in mapping]
for code in target:
    if code not in mapped:
        print(f"  {code}")
