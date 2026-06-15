import re

with open("orders/admin.py") as f:
    content = f.read()

# Fix the split list_display
content = content.replace(
    "    list_display = [\n        'waybill_number', 'delivery_method', 'created_at', 'print_slip'",
    "    list_display = ['id', 'user', 'status_badge', 'total_price', 'waybill_number', 'delivery_method', 'created_at', 'print_slip'"
)

with open("orders/admin.py", "w") as f:
    f.write(content)

print("Done")
