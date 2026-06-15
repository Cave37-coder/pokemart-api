with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

# Replace the era-grouped dropdown with flat release date order
old = """    for era in eras:
        era_sets = [s for s in sets if s.era_id == era.id]
        if not era_sets:
            continue
        html += f'\\n      <optgroup label=\"{era.name}\">'
        for s in era_sets:
            sel = 'selected' if s.code == selected_set_code else ''
            html += f'\\n        <option value=\"{s.code}\" {sel}>[{s.code}] {s.name}</option>'
        html += '\\n      </optgroup>'"""

new = """    for s in sets:
        sel = 'selected' if s.code == selected_set_code else ''
        count = getattr(s, 'card_count', 0)
        count_str = f' ({count} cards)' if count > 0 else ' (empty)'
        html += f'\\n      <option value=\"{s.code}\" {sel}>[{s.code}] {s.name}{count_str}</option>'"""

if old in content:
    content = content.replace(old, new)
    print("Replaced era grouping with flat list")
else:
    print("Pattern not found - checking...")
    idx = content.find("for era in eras:")
    print(f"Found 'for era in eras:' at position: {idx}")

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
