with open('products/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = "    category_slug = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')"
new = "    category_slug = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')\n    pokedex = django_filters.NumberFilter(field_name='pokedex_number', lookup_expr='exact')"

if old in content:
    content = content.replace(old, new)
    print("Pokedex filter added to API")
else:
    print("NOT FOUND")

with open('products/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
