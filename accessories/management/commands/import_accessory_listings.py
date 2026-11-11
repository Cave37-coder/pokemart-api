"""
import_accessory_listings -- 2026-11-11

Creates/updates Accessory rows from a CSV (default: the Temu Oct-2026 order,
accessories/data/temu_nov2026_listings.csv). Dry run by default.

    python manage.py import_accessory_listings              # preview
    python manage.py import_accessory_listings --apply      # write
    python manage.py import_accessory_listings --apply --file path/to.csv

CSV columns: name, category, manufacturer, description, landed_cost,
markup_pct, price, stock, is_active (yes/no), pudo_size (xs/s/m/l/xl), image_file. Matched on exact name, so a
re-run updates description/price/stock instead of duplicating. Rows with
price 0 are created inactive (set the price in admin, then tick Active).

Images: none are set here. Upload each in Django admin (or paste a URL and
run rehost_accessory_images) so it ends up on R2 -- see CLAUDE.md.
Existing listings keep their live stock on re-run (sales are not undone); pass
--reset-stock to force the CSV stock. New listings take the CSV stock.
"""
import csv
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from accessories.models import Accessory

DEFAULT = Path(__file__).resolve().parents[2] / "data" / "temu_nov2026_listings.csv"


# Listings dropped from the catalogue. On --apply these are taken off sale
# (stock 0 + inactive, which also hides their Pile product row) and deleted.
RETIRED = [
    "Stackable Card Storage Boxes - Set of 3, Black (Mixed Colours)",
    "Flip-Top Deck Boxes - Set of 3, Black",
    "Clear Storage Box Set - 30 Boxes in 3 Sizes",
]


class Command(BaseCommand):
    help = "Create/update accessory listings from a CSV (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT))
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--reset-stock", action="store_true",
                            help="Also reset stock on EXISTING listings to the CSV value (off by default so sales are not undone)")
        parser.add_argument("--replace-images", action="store_true",
                            help="Re-upload every CSV image, replacing photos already set")

    def handle(self, *args, **o):
        path = Path(o["file"])
        if not path.exists():
            raise CommandError(f"{path} not found")
        valid = {c for c, _ in Accessory.CATEGORY_CHOICES}
        created = updated = 0
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                name = r["name"].strip()
                cat = r["category"].strip()
                if cat not in valid:
                    raise CommandError(f"{name}: bad category {cat!r}")
                price = Decimal(r["price"] or "0")
                stock = int(r["stock"] or 0)
                active = r["is_active"].strip().lower() == "yes" and price > 0
                fields = dict(
                    category=cat, manufacturer=r["manufacturer"].strip(),
                    description=r["description"].strip(), price=price,
                    stock=stock, is_active=active,
                    pudo_size=(r.get("pudo_size") or "xs").strip().lower() or "xs",
                    price_locked=True,  # hand-set price: TCGCSV sync leaves it alone
                )
                obj = Accessory.objects.filter(name=name).first()
                tag = "UPDATE" if obj else "CREATE"
                shown = obj.stock if (obj and not o["reset_stock"]) else stock
                self.stdout.write(f"  {tag}: {name}  R{price}  stock {shown}{' (kept)' if obj and not o['reset_stock'] else ''}  {'active' if active else 'INACTIVE'}")
                img = (r.get("image_file") or "").strip()
                if img:
                    self.stdout.write(f"      image: {img}")
                if o["apply"]:
                    if obj:
                        for k, v in fields.items():
                            if k == "stock" and not o["reset_stock"]:
                                continue  # keep live stock: sales since the last import must not be undone
                            setattr(obj, k, v)
                        obj.save()
                        updated += 1
                    else:
                        obj = Accessory.objects.create(name=name, **fields)
                        created += 1
                    # Upload the picture to R2 (CLAUDE.md: always R2) unless it
                    # already has one -- never overwrites a photo you uploaded.
                    if img and (o["replace_images"] or not obj.image_url):
                        p = path.parent / "images" / img
                        if p.exists():
                            from accessories.r2 import upload_bytes
                            upload_bytes(obj, p.read_bytes(), filename=p.name)
                        else:
                            self.stdout.write(self.style.WARNING(f"      missing file {p}"))
        removed = 0
        for old in Accessory.objects.filter(name__in=RETIRED):
            self.stdout.write(f"  REMOVE: {old.name}")
            if o["apply"]:
                old.stock = 0
                old.is_active = False
                old.save()  # syncs the Pile product row: inactive, stock 0
                old.delete()
                removed += 1
        if o["apply"]:
            self.stdout.write(self.style.SUCCESS(f"Created {created}, updated {updated}, removed {removed}."))
        else:
            self.stdout.write("Dry run -- nothing written. Add --apply to save.")
