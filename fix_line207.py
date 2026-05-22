with open('products/views.py', encoding='utf-8') as f:
    lines = f.readlines()
lines[206] = '<tbody><tr><td colspan="7" style="height:100px;padding:0"></td></tr>{rows}</tbody>\n'
with open('products/views.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
