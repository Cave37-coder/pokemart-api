# Revert to simple ordering without annotation
# Run: python manage.py shell --command="exec(open('fix_ordering_simple.py').read())"

with open('products/views.py', 'r') as f:
    content = f.read()

# Remove the VARIANT_ORDER Case annotation and restore simple queryset
old = """    VARIANT_ORDER = Case(
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

new = """    queryset = PokemonProduct.objects.filter(is_active=True).select_related(
        'category', 'card_set', 'card_set__era'
    ).prefetch_related('pokemon_types')"""

old_ordering = "    ordering = ['-card_set__release_date', 'card_number', 'variant_sort']"
new_ordering = "    ordering = ['-card_set__release_date', 'card_number', 'variant_override']"

if old in content:
    content = content.replace(old, new)
    print("Queryset reverted")
else:
    print("ERROR: queryset not found")

if old_ordering in content:
    content = content.replace(old_ordering, new_ordering)
    print("Ordering updated")
else:
    print("ERROR: ordering not found")

with open('products/views.py', 'w') as f:
    f.write(content)

print("Done")
