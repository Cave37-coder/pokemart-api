with open('products/views.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'height:100px;padding:0',
    'height:8px;padding:0'
)

with open('products/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
