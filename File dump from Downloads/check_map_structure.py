import json
with open("tcgcsv_db_mapping.json") as f:
    mapping = json.load(f)
print(type(mapping))
if isinstance(mapping, list):
    print("First item:", mapping[0])
elif isinstance(mapping, dict):
    keys = list(mapping.keys())[:5]
    print("Keys sample:", keys)
    print("First value:", mapping[keys[0]])
