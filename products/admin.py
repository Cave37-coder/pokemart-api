from django.contrib import admin
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from .models import PokemonProduct, Category, PokemonType, Era, CardSet, PokedexCollectionEntry


# Michael, 2026-08-08: "yes r2 always for images, set in rules!" -- every
# image URL on the site should end up hosted on R2 (images.pokebulk.co.za),
# never left as an external hotlink, same convention upload_set_images.py /
# upload_to_r2.py already use for card/set images. This is the first place
# that convention is wired into a live admin action instead of a one-off
# local script -- paste any URL into logo_url, select the row(s), run
# "Upload logo(s) to R2" from the action dropdown, done.
def _r2_client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url="https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com",
        aws_access_key_id="fdff88cee69c515cf67d4ae275d1bc72",
        aws_secret_access_key="e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f",
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


R2_BUCKET = "pokebulkcards"
R2_CDN = "https://images.pokebulk.co.za"


def upload_logos_to_r2(modeladmin, request, queryset):
    import requests

    s3 = _r2_client()
    uploaded, skipped, failed = 0, 0, 0
    for era in queryset:
        if not era.logo_url:
            skipped += 1
            continue
        if era.logo_url.startswith(R2_CDN):
            skipped += 1
            continue
        try:
            resp = requests.get(era.logo_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            ext = "png" if ".png" in era.logo_url.lower() else "jpg"
            content_type = "image/png" if ext == "png" else "image/jpeg"
            key = f"eras/logos/{era.code}_logo.{ext}"
            s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType=content_type)
            era.logo_url = f"{R2_CDN}/{key}"
            era.save(update_fields=["logo_url"])
            uploaded += 1
        except Exception as e:
            failed += 1
            modeladmin.message_user(request, f"{era.code}: failed to upload ({e})", level="error")
    modeladmin.message_user(request, f"Uploaded {uploaded}, skipped {skipped} (blank or already on R2), failed {failed}.")


upload_logos_to_r2.short_description = "Upload logo(s) to R2 (re-host external URLs)"


@admin.register(Era)
class EraAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "logo_url"]
    list_editable = ["logo_url"]
    search_fields = ["code", "name"]
    actions = [upload_logos_to_r2]


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
    # wanted_by_count: 2026-08-07, community wishlist feature -- lets Michael
    # sort/scan the whole catalog by customer demand (wishlist adds) right
    # here, no separate reporting page needed. Annotated in get_queryset so
    # it's a real DB-level count (sortable via admin_order_field), not a
    # per-row Python query.
    list_display = ["name", "card_set", "variant_override", "price", "stock", "pos_stock", "is_active", "wanted_by_count"]
    list_filter = ["card_set__era", "card_set", "variant_override", "is_active"]
    search_fields = ["name", "sku", "card_set__name", "card_set__code"]
    list_editable = ["price", "stock"]
    ordering = ["-card_set__release_date", "card_number"]

    def get_queryset(self, request):
        from django.db.models import Count
        return super().get_queryset(request).annotate(_wanted_by_count=Count('wishlisted_by'))

    @admin.display(description="Wanted by", ordering="_wanted_by_count")
    def wanted_by_count(self, obj):
        return obj._wanted_by_count

    fieldsets = [
        ("Card Info", {
            "fields": ["sku", "name", "name_japanese", "card_set", "card_number",
                      "variant_override", "supertype", "rarity", "hp", "stock", "pos_stock", "is_active"]
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


@admin.register(PokedexCollectionEntry)
class PokedexCollectionEntryAdmin(admin.ModelAdmin):
    # Separate from Checklists (see products/models.py) -- this is Michael's
    # visibility into customers' personal Pokedex "owned" marks.
    list_display = ["user", "product", "added_at"]
    list_filter = ["added_at"]
    search_fields = ["user__username", "product__name"]
    autocomplete_fields = ["product"]
    raw_id_fields = ["user"]
