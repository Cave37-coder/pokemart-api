with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

old = ".values('id', 'name', 'card_number', 'variant_override', 'rarity', 'stock', 'price')\n        )"
new = ".values('id', 'name', 'card_number', 'variant_override', 'rarity', 'stock', 'price')\n        )\n        VORDER = {'N': 0, 'RH': 1, 'H': 2}\n        cards = sorted(cards, key=lambda c: (c['card_number'], VORDER.get(c['variant_override'] or 'N', 9)))"

if old in content:
    content = content.replace(old, new)
    with open("products/views.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Done")
else:
    print("Not found - showing values line:")
    for line in content.split("\n"):
        if ".values(" in line and "variant_override" in line:
            print(repr(line))
