with open('products/management/commands/enrich_only.py', 'r') as f:
    content = f.read()

# Fix ALL mode to catch exceptions per set
old = '''            updated, not_found = enrich_set(
                        set_code=code,'''
new = '''            try:
              updated, not_found = enrich_set(
                        set_code=code,'''

# Find the closing of enrich_set call and add except
old2 = '''                stdout=self.stdout,
                )
              total_updated   += updated
              total_not_found += not_found'''
new2 = '''                stdout=self.stdout,
                )
              total_updated   += updated
              total_not_found += not_found
            except Exception as e:
              self.stdout.write(f"  ERROR: {e} — skipping")'''

if old in content:
    content = content.replace(old, new)
    print("Try block added")
else:
    print("NOT FOUND - try block")

if old2 in content:
    content = content.replace(old2, new2)
    print("Except block added")
else:
    print("NOT FOUND - except block")

with open('products/management/commands/enrich_only.py', 'w') as f:
    f.write(content)
