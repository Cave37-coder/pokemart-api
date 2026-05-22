with open("orders/views.py", encoding="utf-8") as f:
    content = f.read()

# Add set code to group header
content = content.replace(
    "key=lambda i: i.product.card_set.name",
    "key=lambda i: (i.product.card_set.name, i.product.card_set.code)"
)
content = content.replace(
    'for set_name, group in groupby(items, key=lambda i: (i.product.card_set.name, i.product.card_set.code)):',
    'for (set_name, set_code), group in groupby(items, key=lambda i: (i.product.card_set.name, i.product.card_set.code)):'
)
content = content.replace(
    'f"{set_name} ({len(cards)} card',
    'f"{set_name} [{set_code}] ({len(cards)} card'
)

# Fix price column width
content = content.replace(
    '<th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="80">Price</th>',
    '<th style="text-align:left;padding:4px 8px;font-size:11px;border-bottom:1px solid #ccc" width="110">Price</th>'
)

with open("orders/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
