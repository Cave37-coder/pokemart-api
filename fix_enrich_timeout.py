with open('products/management/commands/enrich_only.py', 'r') as f:
    content = f.read()

# Fix fetch_cards_from_api to retry on timeout
old = '    r = requests.get(url, headers=headers, timeout=30)'
new = '''    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=60)
            break
        except requests.exceptions.Timeout:
            if attempt < 2:
                print(f"  Timeout, retrying ({attempt+2}/3)...")
                time.sleep(5)
            else:
                raise'''

if old in content:
    content = content.replace(old, new)
    print("Timeout retry added")
else:
    print("NOT FOUND")

with open('products/management/commands/enrich_only.py', 'w') as f:
    f.write(content)
