with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

# Remove the broken Case/When and use simple Python sort after fetch
old = '.annotate(var_order=Case(When(variant_override=\'N\',then=1),When(variant_override=\'RH\',then=2),When(variant_override=\'H\',then=3),default=3,output_field=IntegerField())).order_by(\'card_number\',\'var_order\')'
new = ".order_by('card_number', 'variant_override')"

if old in content:
    content = content.replace(old, new)
    print("Replaced Case/When with simple order")
else:
    print("Pattern not found, showing current order line:")
    for line in content.split("\n"):
        if "order_by" in line and "card_number" in line:
            print(repr(line))

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
