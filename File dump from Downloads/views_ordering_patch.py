# Patch to apply to products/views.py
# Run: python manage.py shell --command="exec(open('views_ordering_patch.py').read())"

# Read current views.py
with open('products/views.py', 'r') as f:
    content = f.read()

# Add import
old_import = "from rest_framework import viewsets, filters"
new_import = "from rest_framework import viewsets, filters\nfrom django.db.models import Case, When, IntegerField, Value"

# Fix ordering in PokemonProductViewSet
old_ordering = "    ordering = ['-card_set__release_date', 'card_number']"
new_ordering = "    ordering = ['-card_set__release_date', 'card_number']"

# Fix the get_queryset to use annotate
old_queryset = """    queryset = PokemonProduct.objects.filter(is_active=True).select_related(
        'category', 'card_set', 'card_set__era'
    ).prefetch_related('pokemon_types')"""

new_queryset = """    VARIANT_ORDER = Case(
        When(variant_override='N', then=Value(0)),
        When(variant_override='1E', then=Value(0)),
        When(variant_override='SH', then=Value(0)),
        When(variant_override='H', then=Value(1)),
        When(variant_override='1E-H', then=Value(1)),
        When(variant_override='1ES-H', then=Value(1)),
        When(variant_override='SH-H', then=Value(1)),
        When(variant_override='MH', then=Value(1)),
        When(variant_override='RH', then=Value(2)),
        When(variant_override='RH-H', then=Value(2)),
        When(variant_override='ERH', then=Value(3)),
        When(variant_override='BRH-PB', then=Value(4)),
        When(variant_override='BRH-FB', then=Value(4)),
        When(variant_override='BRH-QB', then=Value(4)),
        When(variant_override='BRH-LB', then=Value(4)),
        When(variant_override='BRH-DB', then=Value(4)),
        When(variant_override='BRH-R', then=Value(4)),
        When(variant_override='TRH', then=Value(4)),
        When(variant_override='RH-MB', then=Value(5)),
        default=Value(9),
        output_field=IntegerField()
    )
    queryset = PokemonProduct.objects.filter(is_active=True).annotate(
        variant_sort=VARIANT_ORDER
    ).select_related(
        'category', 'card_set', 'card_set__era'
    ).prefetch_related('pokemon_types')"""

old_order_fields = "    ordering_fields = ['price', 'created_at', 'name', 'card_number', 'pokedex_number']"
new_order_fields = "    ordering_fields = ['price', 'created_at', 'name', 'card_number', 'pokedex_number']"

old_default_ordering = "    ordering = ['-card_set__release_date', 'card_number']"
new_default_ordering = "    ordering = ['-card_set__release_date', 'card_number', 'variant_sort']"

if old_import not in content:
    print("ERROR: import not found")
else:
    content = content.replace(old_import, new_import, 1)
    print("Import added")

if old_queryset not in content:
    print("ERROR: queryset not found")
else:
    content = content.replace(old_queryset, new_queryset, 1)
    print("Queryset updated with VARIANT_ORDER")

if old_default_ordering not in content:
    print("ERROR: ordering not found")
else:
    content = content.replace(old_default_ordering, new_default_ordering, 1)
    print("Default ordering updated")

with open('products/views.py', 'w') as f:
    f.write(content)

print("Done! views.py updated.")
