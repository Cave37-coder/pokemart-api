with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'margin-top:8px',
    'margin-top:52px'
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
