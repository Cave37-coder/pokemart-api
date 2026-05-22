with open('products/views.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '<tbody>{rows}</tbody>',
    '<tbody><tr><td colspan="7" style="height:100px;padding:0"></td></tr>{rows}</tbody>'
)

with open('products/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
