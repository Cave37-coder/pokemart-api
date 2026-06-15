with open('products/management/commands/enrich_only.py', 'r') as f:
    content = f.read()

# Find and fix the bad indentation around legalities
old = '        artist          = card.get("artist", "") or ""\n          legalities'
new = '        artist          = card.get("artist", "") or ""\n        legalities'

if old in content:
    content = content.replace(old, new)
    print("Fixed legalities indent")
else:
    idx = content.find('legalities')
    print(repr(content[idx-20:idx+200]))

# Fix all the legal_ lines too
for field in ['legal_standard', 'legal_expanded', 'legal_unlimited']:
    bad = f'          {field}'
    good = f'        {field}'
    if bad in content:
        content = content.replace(bad, good)
        print(f"Fixed {field} indent")

with open('products/management/commands/enrich_only.py', 'w') as f:
    f.write(content)
