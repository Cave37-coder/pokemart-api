with open('products/urls.py', 'r') as f:
    content = f.read()

old = 'path("stock/entry/", views.stock_entry, name="stock-entry"),'
new = 'path("stock/entry/", views.stock_entry, name="stock-entry"),\n    path("stock/bundles/", views.bundle_stock_entry, name="bundle-stock-entry"),'

if old in content:
    content = content.replace(old, new)
    print("URL added")
else:
    print("NOT FOUND - checking...")
    print(content[:500])

with open('products/urls.py', 'w') as f:
    f.write(content)
