with open("import_stock.py", encoding="utf-8") as f:
    content = f.read()
content = content.replace(
    '"store_data_20260518_140458.csv"',
    r'"C:\Downloads\store_data_20260522_110808.csv"'
)
with open("import_stock.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
