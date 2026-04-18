from django.contrib import admin
from .models import PokemonProduct, Category, PokemonType, Era, CardSet


@admin.register(Era)
class EraAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']


@admin.register(CardSet)
class CardSetAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'era']
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
    list_display = ['pb_id', 'sku', 'name', 'card_set', 'rarity', 'price', 'stock', 'is_active']
    list_filter = ['rarity', 'category', 'card_set__era', 'is_active']
    search_fields = ['name', 'pb_id', 'sku', 'tcgplayer_id', 'gengar_id']
    list_editable = ['price', 'stock', 'is_active']
    readonly_fields = ['pb_id', 'sku']
    fieldsets = (
        ('Identifiers', {
            'fields': ('pb_id', 'sku', 'tcgplayer_id', 'gengar_id')
        }),
        ('Product Info', {
            'fields': ('name', 'description', 'category', 'card_set', 'pokemon_types',
                      'rarity', 'pokedex_number', 'card_number', 'variant_override')
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'stock', 'image', 'is_active')
        }),
    )