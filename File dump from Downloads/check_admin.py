import re

with open("orders/admin.py") as f:
    content = f.read()

# Check if print_slip method exists
if "def print_slip" in content:
    print("print_slip method exists")
else:
    print("print_slip method MISSING")

# Check list_display
for line in content.split("\n"):
    if "list_display" in line or "print_slip" in line:
        print(repr(line))
