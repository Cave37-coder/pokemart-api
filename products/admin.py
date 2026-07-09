from django.contrib import admin
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from .models import PokemonProduct, Category, PokemonType, Era, CardSet


@admin.register(Era)
class EraAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
    search_fields = ["code", "name"]


@admin.register(CardSet)
class CardSetAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "era", "total_cards", "release_date"]
    list_filter = ["era"]
    search_fields = ["code", "name"]


@admin.register(PokemonType)
class PokemonTypeAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


class ProductAutocompleteJsonView(AutocompleteJsonView):
    """
    Confirmed via the actual browser Network tab request URL:
    /admin/autocomplete/ is ONE global endpoint owned by AdminSite, shared
    by every autocomplete field across the whole admin -- not something any
    per-model ModelAdmin.get_urls() override can reach (an earlier attempt
    at this fix). This view gets wired in at the project urls.py level
    instead, ahead of admin.site.urls, so Django's resolver matches it
    first. Falls back to default behaviour for any model other than
    PokemonProduct, since this same global URL serves every autocomplete
    field in the admin, not just this one.
    """
    def serialize_result(self, obj, to_field_name):
        if obj.__class__.__name__ == 'PokemonProduct':
            set_label = obj.card_set.name if obj.card_set else 'No Set'
            set_code = f" [{obj.card_set.code}]" if obj.card_set else ''
            number = f" #{obj.card_number}" if obj.card_number else ''
            variant = f" ({obj.variant_override})" if obj.variant_override else ''
            text = f"{obj.name} — {set_label}{set_code}{number}{variant}"
            return {"id": str(getattr(obj, to_field_name)), "text": text}
        return super().serialize_result(obj, to_field_name)


@admin.register(PokemonProduct)
class PokemonProductAdmin(admin.ModelAdmin):
    list_display = ["name", "card_set", "variant_override", "price", "stock", "is_active"]
    list_filter = ["card_set__era", "card_set", "variant_override", "is_active"]
    search_fields = ["name", "sku", "card_set__name", "card_set__code"]
    list_editable = ["price", "stock"]
    ordering = ["-card_set__release_date", "card_number"]

    fieldsets = [
        ("Card Info", {
            "fields": ["sku", "name", "name_japanese", "card_set", "card_number",
                      "variant_override", "supertype", "rarity", "hp", "stock", "is_active"]
        }),
        ("Standard Prices (ZAR)", {
            "fields": ["price", "price_normal", "price_holo", "price_reverse_holo", "price_first_edition"],
        }),
        ("Ball Variant Prices (ZAR)", {
            "fields": ["price_pokeball", "price_masterball", "price_friendball",
                      "price_loveball", "price_quickball", "price_duskball"],
            "description": "Set individual prices for each ball variant. Also update the Price field above.",
        }),
        ("Images", {
            "fields": ["image_url", "image_small_url"],
            "classes": ["collapse"]
        }),
        ("Attacks & Abilities", {
            "fields": ["ability_name", "ability_type", "ability_text",
                      "attack_1_name", "attack_1_damage", "attack_1_text",
                      "attack_2_name", "attack_2_damage", "attack_2_text"],
            "classes": ["collapse"]
        }),
    ]
