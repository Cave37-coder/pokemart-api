from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Accessory


class AccessoryAdminForm(forms.ModelForm):
    # Not a model field: Railway's filesystem is ephemeral, so a dropped-in
    # photo goes straight to R2 and only the R2 URL is stored (same approach
    # as the Era logo_file upload in products/admin.py).
    image_file = forms.ImageField(
        required=False,
        label="Upload image",
        help_text="Drop in your own photo -- it is uploaded to R2 and replaces the image URL.",
    )

    class Meta:
        model = Accessory
        fields = "__all__"


def rehost_images_to_r2(modeladmin, request, queryset):
    from .r2 import rehost_from_url, is_on_r2, NoSourceImage
    done = skipped = failed = 0
    for acc in queryset:
        if is_on_r2(acc.image_url):
            skipped += 1
            continue
        try:
            if rehost_from_url(acc):
                done += 1
            else:
                skipped += 1
        except NoSourceImage:
            skipped += 1
            modeladmin.message_user(request, f"{acc.sku}: TCGplayer has no photo -- upload your own.", level="warning")
        except Exception as e:
            failed += 1
            modeladmin.message_user(request, f"{acc.sku}: failed ({e})", level="error")
    modeladmin.message_user(request, f"Re-hosted {done} image(s) on R2, skipped {skipped} (already on R2 / no source), failed {failed}.")


rehost_images_to_r2.short_description = "Re-host image(s) on R2 (from TCGplayer / external URL)"


@admin.register(Accessory)
class AccessoryAdmin(admin.ModelAdmin):
    """Michael's full-access management screen -- unrestricted regardless of
    stock/active state (the public API is what enforces "customers only see
    what's in Stock", not this). list_editable on price/stock/is_active
    means the common case (restock, reprice, take something off sale) never
    needs to open the full edit form. The "Add Accessory" button (top right
    of the changelist) IS the easy-add function for anything not pulled in
    by the TCGCSV import -- only name/category/price are required, so a
    one-off item takes seconds to add.

    Stock bought from a seller should normally go through the staff
    Buying Invoice (Accessories & sealed tab) so the cost is recorded --
    editing stock here is for counts/corrections."""
    form = AccessoryAdminForm
    list_display = ["thumb", "sku", "name", "category", "manufacturer", "price", "price_locked", "stock", "in_stock_display", "is_active"]
    list_display_links = ["sku", "name"]
    list_filter = ["category", "is_active", "price_locked", "manufacturer"]
    search_fields = ["sku", "name", "manufacturer", "description", "barcode", "=tcgcsv_product_id"]
    list_editable = ["price", "stock", "is_active"]
    ordering = ["-created_at"]
    actions = [rehost_images_to_r2]
    readonly_fields = ["image_preview", "sku", "image_source_url", "tcgcsv_product_id", "tcgcsv_category_id", "tcgplayer_url", "source_price_usd", "created_at", "updated_at"]

    fieldsets = [
        ("Accessory Info", {
            "fields": ["name", "category", "manufacturer", "description", "barcode"],
        }),
        ("Image", {
            "fields": ["image_preview", "image_file", "image_url"],
        }),
        ("Pricing & Stock", {
            "fields": ["price", "price_locked", "stock", "is_active"],
        }),
        ("Import Info (read-only)", {
            "fields": ["sku", "tcgcsv_product_id", "tcgcsv_category_id", "tcgplayer_url", "source_price_usd", "image_source_url", "created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="In Stock", boolean=True)
    def in_stock_display(self, obj):
        return obj.in_stock

    @admin.display(description="")
    def thumb(self, obj):
        if not obj.image_url:
            return ""
        return format_html('<img src="{}" style="height:40px;width:40px;object-fit:contain" />', obj.image_url)

    @admin.display(description="Current image")
    def image_preview(self, obj):
        if not obj or not obj.image_url:
            return "No image"
        return format_html('<img src="{}" style="max-height:200px;max-width:200px;object-fit:contain" />', obj.image_url)

    def save_model(self, request, obj, form, change):
        # A price typed in here is Michael's price -- keep it through re-syncs.
        if change and "price" in getattr(form, "changed_data", []) and "price_locked" not in form.changed_data:
            obj.price_locked = True
        super().save_model(request, obj, form, change)
        uploaded = form.cleaned_data.get("image_file") if hasattr(form, "cleaned_data") else None
        if uploaded:
            from .r2 import upload_bytes
            try:
                upload_bytes(obj, uploaded.read(), getattr(uploaded, "content_type", ""), uploaded.name)
            except Exception as e:
                self.message_user(request, f"Saved, but the image upload to R2 failed: {e}", level="error")
        elif "image_url" in getattr(form, "changed_data", []) and obj.image_url:
            # A pasted external URL is re-hosted straight away.
            from .r2 import rehost_from_url, is_on_r2
            if not is_on_r2(obj.image_url):
                try:
                    rehost_from_url(obj, obj.image_url)
                except Exception as e:
                    self.message_user(request, f"Saved, but re-hosting the image on R2 failed: {e}", level="warning")
