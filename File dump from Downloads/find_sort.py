with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

# Find the VORDER sort line
for i, line in enumerate(content.split("\n")):
    if "VORDER" in line or "sorted(cards" in line:
        print(i, repr(line))
