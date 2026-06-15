with open('products/views.py', 'r') as f:
    content = f.read()

# Add legality filter to PokemonProductViewSet's get_queryset or filter_queryset
# Find where the era filter is applied and add legality there
old = '''    def get_queryset(self):
        queryset = PokemonProduct.objects.filter(is_active=True).select_related(
            'category', 'card_set', 'card_set__era'
        ).prefetch_related('pokemon_types')
        return queryset'''

new = '''    def get_queryset(self):
        queryset = PokemonProduct.objects.filter(is_active=True).select_related(
            'category', 'card_set', 'card_set__era'
        ).prefetch_related('pokemon_types')

        legality = self.request.query_params.get('legality', '')
        if legality == 'standard':
            queryset = queryset.filter(card_set__regulation_mark__in=['H', 'I', 'J'])
        elif legality == 'expanded':
            queryset = queryset.filter(card_set__regulation_mark__in=['D', 'E', 'F', 'G', 'H', 'I', 'J'])
        elif legality == 'rotated_g':
            queryset = queryset.filter(card_set__regulation_mark='G')
        elif legality == 'rotated_f':
            queryset = queryset.filter(card_set__regulation_mark='F')

        return queryset'''

if old in content:
    content = content.replace(old, new)
    print("Legality filter added to get_queryset")
else:
    print("get_queryset NOT FOUND - checking structure")
    idx = content.find('def get_queryset')
    print(repr(content[idx:idx+300]))

with open('products/views.py', 'w') as f:
    f.write(content)
