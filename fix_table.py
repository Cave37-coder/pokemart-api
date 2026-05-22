with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    '<table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px #0001">',
    '<table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px #0001;margin-top:8px">'
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
