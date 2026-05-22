with open('products/views.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '<tbody><tr><td colspan="7" style="padding:0;height:8px"></td></tr>{rows}</tbody>',
    '<tbody>{rows}</tbody>'
)

with open('products/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
