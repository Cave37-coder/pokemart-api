with open('products/views.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace('margin-top:80px', 'margin-top:0')
content = content.replace('top:52px', 'top:53px')

with open('products/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
