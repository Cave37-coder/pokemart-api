with open('products/management/commands/sync_tcgcsv.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'defaults={"name": name, "sort_order": sort_order}',
    'defaults={"name": name}'
)

with open('products/management/commands/sync_tcgcsv.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
