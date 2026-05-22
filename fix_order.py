with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    ".order_by('card_number', '-variant_override')",
    ".order_by('card_number')"
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
