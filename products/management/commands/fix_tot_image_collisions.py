"""
Fixes image_url/image_small_url collisions in the Trick-or-Trade sets
(TT22/TT23/TT24, and any other TOT-era set with the same pattern).

Root cause (confirmed 2026-06-21): these sets are reprint compilations
pulling cards from several different original sets. Two unrelated cards
can share the same printed card_number (e.g. "Mimikyu - 037/091" and
"Lampent - 037/167" are both card #37, just from different source sets
with different totals). The original image sync used card_number alone
to build the R2 filename (TT24_037.jpg), so the second product synced
silently overwrote the first card's image file.

Fix: for every affected product, point image_url/image_small_url directly
at TCGplayer's own CDN using tcgcsv_product_id, which is guaranteed unique
per product and needs no new upload/credentials -- this exact CDN pattern
is already used as a fallback elsewhere in this catalog.

Usage:
    python manage.py fix_tot_image_collisions --dry-run
    python manage.py fix_tot_image_collisions
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from products.models import PokemonProduct

AFFECTED_SET_CODES = ["TT22", "TT23", "TT24"]
TCGPLAYER_CDN_TEMPLATE = "https://tcgplayer-cdn.tcgplayer.com/product/{product_id}_200w.jpg"


class Command(BaseCommand):
    help = "Fix image_url collisions in Trick-or-Trade sets caused by card_number reuse across merged reprint sources."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        total_fixed = 0
        total_skipped_no_tcgcsv_id = 0

        for set_code in AFFECTED_SET_CODES:
            colliding_urls = (
                PokemonProduct.objects.filter(card_set__code=set_code)
                .values("image_url")
                .annotate(n=Count("id"))
                .filter(n__gt=1)
            )

            if not colliding_urls:
                self.stdout.write(f"[{set_code}] no collisions found.")
                continue

            self.stdout.write(f"[{set_code}] {len(colliding_urls)} colliding filename(s):")

            for entry in colliding_urls:
                old_url = entry["image_url"]
                affected = list(
                    PokemonProduct.objects.filter(card_set__code=set_code, image_url=old_url)
                )

                for p in affected:
                    if not p.tcgcsv_product_id:
                        self.stdout.write(self.style.WARNING(
                            f"  SKIP id={p.id} '{p.name}' -- no tcgcsv_product_id, can't build a unique CDN URL"
                        ))
                        total_skipped_no_tcgcsv_id += 1
                        continue

                    new_url = TCGPLAYER_CDN_TEMPLATE.format(product_id=p.tcgcsv_product_id)
                    self.stdout.write(
                        f"  {p.name} ({p.number}) | {old_url} -> {new_url}"
                    )

                    if not dry_run:
                        p.image_url = new_url
                        p.image_small_url = new_url
                        p.save(update_fields=["image_url", "image_small_url"])

                    total_fixed += 1

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"Dry run -- would fix {total_fixed} product(s). "
                f"{total_skipped_no_tcgcsv_id} skipped (no tcgcsv_product_id)."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Fixed {total_fixed} product(s). "
                f"{total_skipped_no_tcgcsv_id} skipped (no tcgcsv_product_id, need manual review)."
            ))
