with open("orders/views.py", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "set_name} (" in line and "set_code" not in line:
        lines[i] = line.replace(
            "{set_name} ({len(cards)}",
            "{set_name} [{set_code}] ({len(cards)}"
        )
        print(f"Fixed line {i+1}")

with open("orders/views.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Done")
