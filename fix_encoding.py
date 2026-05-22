with open("orders/views.py") as f:
    content = f.read()

content = content.replace(
    "return HttpResponse(html)",
    'return HttpResponse(html, content_type="text/html; charset=utf-8")'
)

with open("orders/views.py", "w") as f:
    f.write(content)
print("Done")
