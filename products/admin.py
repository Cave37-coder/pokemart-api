from django.contrib import admin
from .models import PokemonProduct, Category, PokemonType

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
    list_display = ['name', 'category', 'rarity', 'price', 'stock', 'is_active']
    list_filter = ['rarity', 'category', 'pokemon_types', 'is_active']
    search_fields = ['name', 'set_name']
    list_editable = ['price', 'stock', 'is_active']
