with open('products/views.py', 'r') as f:
    content = f.read()

old = "    rarity = django_filters.CharFilter(field_name='rarity', lookup_expr='iexact')"
new = "    rarity = django_filters.CharFilter(field_name='rarity', lookup_expr='iexact')\n    category_slug = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')"

if old in content:
    content = content.replace(old, new)
    print("Category slug filter added")
else:
    print("NOT FOUND")

with open('products/views.py', 'w') as f:
    f.write(content)
