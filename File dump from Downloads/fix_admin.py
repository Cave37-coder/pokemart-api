import re

with open("orders/admin.py") as f:
    content = f.read()

content = content.replace(
    "list_display = [\n        'id', 'user', 'status_badge', 'total_price',\n        'waybill_number', 'delivery_method', 'created_at'\n    ]",
    "list_display = [\n        'id', 'user', 'status_badge', 'total_price',\n        'waybill_number', 'delivery_method', 'created_at', 'print_slip'\n    ]"
)

with open("orders/admin.py", "w") as f:
    f.write(content)

print("Done")
