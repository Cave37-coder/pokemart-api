"""
accessories/r2.py -- re-host accessory images on Cloudflare R2.

CLAUDE.md rule "Image hosting -- always R2": every stored image URL must end
up on https://images.pokebulk.co.za, never an external hotlink. Used by
sync_accessories (on import), the buying-invoice "new product" form, the
admin upload field / re-host action, and rehost_accessory_images.

Key convention: accessories/<category>/<sku>.<ext>
Reuses the existing _r2_client() / R2_BUCKET / R2_CDN from products.admin
(CLAUDE.md: reuse that pattern, don't invent a new one).
"""
import requests

TCGPLAYER_IMAGE = "https://tcgplayer-cdn.tcgplayer.com/product/{pid}_200w.jpg"
# Full browser UA -- same as the card image scripts that already pull from
# the TCGplayer CDN successfully.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


class NoSourceImage(Exception):
    """The source has no image (TCGplayer's CDN answers 403/404 for a
    product that never had a photo uploaded). Not a real failure -- the
    product just needs its own photo (Django admin -> Upload image)."""


def _r2():
    from products.admin import _r2_client, R2_BUCKET, R2_CDN
    return _r2_client(), R2_BUCKET, R2_CDN


def is_on_r2(url):
    from products.admin import R2_CDN
    return bool(url) and url.startswith(R2_CDN)


def _ext_for(content_type, fallback_name=""):
    ct = (content_type or "").lower()
    name = (fallback_name or "").lower()
    if "png" in ct or name.endswith(".png"):
        return "png", "image/png"
    if "webp" in ct or name.endswith(".webp"):
        return "webp", "image/webp"
    return "jpg", "image/jpeg"


def upload_bytes(accessory, data, content_type="", filename=""):
    """Upload raw image bytes for `accessory` (must already be saved, so it
    has a sku) and point image_url at R2. Returns the new URL."""
    s3, bucket, cdn = _r2()
    ext, ct = _ext_for(content_type, filename)
    key = f"accessories/{accessory.category or 'other'}/{accessory.sku}.{ext}"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=ct)
    url = f"{cdn}/{key}"
    type(accessory).objects.filter(pk=accessory.pk).update(image_url=url)
    accessory.image_url = url
    return url


def rehost_from_url(accessory, source_url=None):
    """Download `source_url` (default: image_source_url, else the current
    external image_url, else the TCGplayer 200w image for tcgcsv_product_id)
    and re-host it on R2. Returns the new URL, or None when there is nothing
    to fetch / it is already on R2. Raises on download/upload failure."""
    src = (source_url
           or accessory.image_source_url
           or (accessory.image_url if not is_on_r2(accessory.image_url) else "")
           or (TCGPLAYER_IMAGE.format(pid=accessory.tcgcsv_product_id) if accessory.tcgcsv_product_id else ""))
    if not src or is_on_r2(src):
        return None
    resp = requests.get(src, timeout=20, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*"})
    if resp.status_code in (403, 404):
        raise NoSourceImage(f"no image at {src}")
    resp.raise_for_status()
    if not resp.content or not resp.headers.get("Content-Type", "image").startswith("image"):
        raise NoSourceImage(f"no image at {src}")
    if accessory.image_source_url != src:
        type(accessory).objects.filter(pk=accessory.pk).update(image_source_url=src)
        accessory.image_source_url = src
    return upload_bytes(accessory, resp.content, resp.headers.get("Content-Type", ""), src)
