with open("orders/views.py") as f:
    content = f.read()

content = content.replace("PokéBulk SA — Packing Slip", "PokeBulk SA - Packing Slip")
content = content.replace("⚡ PokéBulk SA — Packing Slip", "PokeBulk SA - Packing Slip")
content = content.replace("📦 Delivery Details", "Delivery Details")
content = content.replace("📝 Customer Note", "Customer Note")
content = content.replace("🖨 Print", "Print")
content = content.replace("Cards to Pack — Grouped by Set", "Cards to Pack - Grouped by Set")
content = content.replace("□", "[  ]")
content = content.replace("PokéBulk SA —", "PokeBulk SA -")

with open("orders/views.py", "w") as f:
    f.write(content)
print("Done")
