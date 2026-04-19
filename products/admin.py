from django.contrib import admin
from .models import PokemonProduct, Category, PokemonType, Era, CardSet


@admin.register(Era)
class EraAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']


@admin.register(CardSet)
class CardSetAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'era', 'total_cards', 'release_date']
    list_filter = ['era']
    search_fields = ['code', 'name']


@admin.register(PokemonType)
class PokemonTypeAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(PokemonProduct)
class PokemonProductAdmin(admin.ModelAdmin):
    list_display = ['pb_id', 'sku', 'name', 'card_set', 'rarity', 'hp', 'artist', 'price', 'stock', 'is_active']
    list_filter = ['rarity', 'category', 'card_set__era', 'supertype', 'is_active']
    search_fields = ['name', 'pb_id', 'sku', 'tcgplayer_id', 'gengar_id', 'artist']
    list_editable = ['price', 'stock', 'is_active']
    readonly_fields = ['pb_id', 'sku']
    fieldsets = (
        ('Identifiers', {
            'fields': ('pb_id', 'sku', 'tcgplayer_id', 'gengar_id')
        }),
        ('Product Info', {
            'fields': (
                'name', 'description', 'flavour_text', 'category',
                'card_set', 'pokemon_types', 'rarity',
                'pokedex_number', 'card_number', 'variant_override'
            )
        }),
        ('Card Stats', {
            'fields': (
                'supertype', 'card_subtypes', 'hp', 'artist',
                'weakness_type', 'weakness_value',
                'resistance_type', 'resistance_value', 'retreat_cost'
            )
        }),
        ('Attacks', {
            'fields': (
                'attack_1_name', 'attack_1_damage', 'attack_1_text',
                'attack_2_name', 'attack_2_damage', 'attack_2_text',
            )
        }),
        ('Media', {
            'fields': ('image', 'image_url', 'image_small_url')
        }),
        ('Pricing', {
            'fields': (
                'price', 'price_normal', 'price_holo',
                'price_reverse_holo', 'price_first_edition'
            )
        }),
        ('Stock', {
            'fields': ('stock', 'is_active')
        }),
    )