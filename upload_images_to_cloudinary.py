# -*- coding: utf-8 -*-
"""
upload_images_to_cloudinary.py - PokeBulk SA
Uploads all card images to Cloudinary and updates DB image_url fields.
Run with DATABASE_URL uncommented in .env

Usage:
  python upload_images_to_cloudinary.py --dry-run
  python upload_images_to_cloudinary.py
  python upload_images_to_cloudinary.py --set MEG
  python upload_images_to_cloudinary.py --overwrite
"""
import os, django, sys, time, requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import cloudinary
import cloudinary.uploader
from products.models import PokemonProduct, CardSet
from django.db import transaction

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name = "dpdulaufd",
    api_key    = "613679581116384",
    api_secret = "nIcFekH7wHLFfOKpkIX7dPERQ_A",
    secure     = True
)

def upload_image(image_url, public_id):
    """Upload image to Cloudinary and return new URL"""
    try:
        result = cloudinary.uploader.upload(
            image_url,
            public_id   = public_id,
            folder      = "pokebulk/cards",
            overwrite   = False,
            resource_type = "image",
            timeout     = 30,
        )
        return result.get("secure_url"), None
    except Exception as e:
        return None, str(e)


def make_public_id(product):
    """Generate a unique Cloudinary public ID for a card"""
    set_code = product.card_set.code if product.card_set else "unknown"
    pid      = product.tcgcsv_product_id or product.id
    variant  = product.variant_override or "N"
    return f"{set_code}_{pid}_{variant}".replace(" ", "_").lower()


def is_cloudinary_url(url):
    return url and "res.cloudinary.com" in url


def main():
    dry_run   = "--dry-run"  in sys.argv
    overwrite = "--overwrite" in sys.argv
    set_filter = None
    if "--set" in sys.argv:
        idx = sys.argv.index("--set")
        if idx + 1 < len(sys.argv):
            set_filter = sys.argv[idx + 1].upper()

    print("PokeBulk Cloudinary Image Upload")
    print(f"Dry run: {dry_run} | Overwrite: {overwrite} | Set filter: {set_filter or 'ALL'}")
    print("=" * 60)

    # Build queryset
    qs = PokemonProduct.objects.select_related('card_set').exclude(image_url='')
    if set_filter:
        qs = qs.filter(card_set__code=set_filter)
    if not overwrite:
        # Only process non-Cloudinary images
        qs = qs.exclude(image_url__contains='res.cloudinary.com')

    total = qs.count()
    print(f"Records to process: {total}")

    uploaded = failed = skipped = 0
    to_update = []

    for i, product in enumerate(qs, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{total} | Uploaded:{uploaded} Failed:{failed}")

        if is_cloudinary_url(product.image_url) and not overwrite:
            skipped += 1
            continue

        public_id = make_public_id(product)

        if dry_run:
            print(f"  [DRY] {product.card_set.code} #{product.card_number} "
                  f"{(product.name or '')[:30]} -> pokebulk/cards/{public_id}")
            uploaded += 1
            continue

        new_url, error = upload_image(product.image_url, public_id)

        if error:
            failed += 1
            if failed <= 10:
                print(f"  FAILED: {product.name[:30]} | {error}")
            time.sleep(0.5)
            continue

        product.image_url       = new_url
        product.image_small_url = new_url
        to_update.append(product)
        uploaded += 1

        # Batch save every 50
        if len(to_update) >= 50:
            with transaction.atomic():
                PokemonProduct.objects.bulk_update(
                    to_update,
                    ['image_url', 'image_small_url'],
                    batch_size=200
                )
            print(f"  Saved {len(to_update)} records...")
            to_update = []

        time.sleep(0.1)  # Rate limit

    # Save remaining
    if to_update and not dry_run:
        with transaction.atomic():
            PokemonProduct.objects.bulk_update(
                to_update,
                ['image_url', 'image_small_url'],
                batch_size=200
            )

    print(f"\n{'='*60}")
    print(f"DONE")
    print(f"  Uploaded:  {uploaded}")
    print(f"  Failed:    {failed}")
    print(f"  Skipped:   {skipped}")
    if dry_run:
        print(f"  (DRY RUN - nothing saved)")


if __name__ == "__main__":
    main()
