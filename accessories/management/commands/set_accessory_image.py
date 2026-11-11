"""
set_accessory_image -- 2026-11-11

Upload one photo to R2 (images.pokebulk.co.za) and set it as an accessory's
image. Matches by SKU or by a name fragment.

    python manage.py set_accessory_image --sku ACC-0546 --file accessories/data/images/151-ultra-premium-deck-box.jpg
    python manage.py set_accessory_image --name "151 Ultra-Premium" --file <path> --overwrite
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from accessories.models import Accessory
from accessories.r2 import upload_bytes


class Command(BaseCommand):
    help = "Upload a local image to R2 and set it on an accessory."

    def add_arguments(self, parser):
        parser.add_argument("--sku")
        parser.add_argument("--name", help="Name fragment (must match exactly one accessory)")
        parser.add_argument("--file", required=True)
        parser.add_argument("--overwrite", action="store_true", help="Replace an existing image")

    def handle(self, *args, **o):
        qs = Accessory.objects.all()
        if o["sku"]:
            qs = qs.filter(sku=o["sku"])
        elif o["name"]:
            qs = qs.filter(name__icontains=o["name"])
        else:
            raise CommandError("Give --sku or --name")
        if qs.count() != 1:
            raise CommandError(f"Matched {qs.count()} accessories: {[a.name for a in qs[:5]]}")
        acc = qs.first()
        p = Path(o["file"])
        if not p.exists():
            raise CommandError(f"{p} not found")
        if acc.image_url and not o["overwrite"]:
            self.stdout.write(f"{acc.name} already has an image ({acc.image_url}). Use --overwrite to replace.")
            return
        url = upload_bytes(acc, p.read_bytes(), filename=p.name)
        self.stdout.write(self.style.SUCCESS(f"{acc.sku} {acc.name} -> {url}"))
