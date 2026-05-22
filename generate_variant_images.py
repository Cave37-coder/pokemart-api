"""
Management command: generate_variant_images
============================================
Reads clean originals from media/card_images/originals/{set}/{num}.png
and generates a watermarked variant copy for every non-Normal PokemonProduct.

The watermark is confined strictly to the art-box zone of the card
(top 20% – 65% of card height) and is never applied to N (Normal) variants.

Usage:
    python manage.py generate_variant_images
    python manage.py generate_variant_images --set sv3pt5
    python manage.py generate_variant_images --force
    python manage.py generate_variant_images --dry-run
    python manage.py generate_variant_images --opacity 0.18

Output structure:
    media/card_images/variants/{set_code}/{number}_{variant}.png

Requires:
    pip install Pillow --break-system-packages
"""

import os
import math
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

# Variants that should NOT get a watermark overlay
NO_OVERLAY_VARIANTS = {"N", "DR"}

# Card zone ratios  (fraction of total card height)
# Pokémon TCG card proportions: 63mm × 88mm  ≈  ratio 0.716
ART_TOP_RATIO    = 0.115   # where the art box starts
ART_BOTTOM_RATIO = 0.620   # where the art box ends

# Overlay style
STORE_NAME     = "PokéBulk SA"
TEXT_COLOR     = (255, 255, 255)   # white — alpha set per opacity option
FONT_SCALE     = 0.055             # store name font size as fraction of card width
VARIANT_SCALE  = 0.040
LINE_GAP_RATIO = 0.015             # gap between two text lines as fraction of card height

# Human-readable variant labels
VARIANT_LABELS = {
    "H":      "Holofoil",
    "RH":     "Reverse Holo",
    "ERH":    "ETB Reverse Holo",
    "RH-PB":  "Poké Ball Holo",
    "RH-MB":  "Master Ball Holo",
    "BRH-FB": "Fast Ball Holo",
    "BRH-LB": "Luxury Ball Holo",
    "BRH-QB": "Quick Ball Holo",
    "BRH-DB": "Dusk Ball Holo",
    "BRH-R":  "Rocket Ball Holo",
    "AS":     "Ace Spec",
    "MH":     "Mirror Holo",
    "1st":    "1st Edition",
    "IR":     "Illustration Rare",
    "SIR":    "Special Illustration Rare",
    "HR":     "Hyper Rare",
}


class Command(BaseCommand):
    help = "Generate watermarked variant images from clean card originals"

    def add_arguments(self, parser):
        parser.add_argument("--set",     dest="set_code", help="Only process this set code")
        parser.add_argument("--force",   action="store_true", help="Regenerate even if output already exists")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without writing files")
        parser.add_argument("--opacity", type=float, default=0.17,
                            help="Watermark opacity 0.0–1.0 (default 0.17)")

    def handle(self, *args, **options):
        if not PILLOW_OK:
            self.stderr.write(self.style.ERROR(
                "Pillow is not installed. Run:\n"
                "  pip install Pillow --break-system-packages"
            ))
            return

        from products.models import PokemonProduct

        set_filter = options["set_code"]
        force      = options["force"]
        dry_run    = options["dry_run"]
        opacity    = max(0.05, min(0.40, options["opacity"]))

        orig_base    = Path(settings.MEDIA_ROOT) / "card_images" / "originals"
        variant_base = Path(settings.MEDIA_ROOT) / "card_images" / "variants"
        variant_base.mkdir(parents=True, exist_ok=True)

        qs = PokemonProduct.objects.select_related("card_set").all()
        if set_filter:
            qs = qs.filter(card_set__code=set_filter)

        # Only products with a variant that needs an overlay
        qs = qs.exclude(variant_override__in=["", None] + list(NO_OVERLAY_VARIANTS))

        total   = qs.count()
        done    = 0
        skipped = 0
        missing = []

        self.stdout.write(self.style.HTTP_INFO(
            f"\n{'[DRY RUN] ' if dry_run else ''}Processing {total} variant products\n"
        ))

        for product in qs:
            set_code = product.card_set.code if product.card_set else None
            num      = product.card_number
            variant  = product.variant_override

            if not set_code or not num or not variant:
                continue

            orig_file = orig_base / set_code / f"{num}.png"
            if not orig_file.exists():
                missing.append(f"{set_code}/{num}")
                continue

            safe_variant = variant.replace("/", "-").replace("\\", "-")
            out_dir  = variant_base / set_code
            out_file = out_dir / f"{num}_{safe_variant}.png"

            if out_file.exists() and not force:
                skipped += 1
                continue

            if dry_run:
                label = VARIANT_LABELS.get(variant, variant)
                self.stdout.write(f"  [DRY] {set_code}/{num}_{safe_variant}.png  →  '{label}'")
                done += 1
                continue

            try:
                self._apply_overlay(orig_file, out_dir, out_file, variant, opacity)
                done += 1
                self.stdout.write(f"  ✓ {set_code}/{num}_{safe_variant}.png")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ✗ {set_code}/{num}: {e}"))

        # ── Summary ──────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Generated  : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Skipped    : {skipped}  (already exists)"))
        if missing:
            unique_missing = sorted(set(missing))
            self.stdout.write(self.style.WARNING(
                f"  No original: {len(unique_missing)} cards  "
                f"(run download_card_images first)"
            ))
            for m in unique_missing[:15]:
                self.stdout.write(f"    - {m}")
            if len(unique_missing) > 15:
                self.stdout.write(f"    … and {len(unique_missing) - 15} more")
        self.stdout.write("─" * 50 + "\n")

    # ── Core overlay logic ────────────────────────────────────────────────────

    def _apply_overlay(self, orig_file, out_dir, out_file, variant, opacity):
        """
        Open the original card image, draw a two-line semi-transparent
        watermark confined strictly to the art-box zone, then save.
        """
        out_dir.mkdir(parents=True, exist_ok=True)

        img = Image.open(orig_file).convert("RGBA")
        w, h = img.size

        # Art-box bounds in pixels
        art_top    = int(h * ART_TOP_RATIO)
        art_bottom = int(h * ART_BOTTOM_RATIO)
        art_h      = art_bottom - art_top
        art_mid_y  = art_top + art_h // 2

        # ── Create transparent overlay the same size as the full card ────────
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        # Font sizes
        font_size_store   = max(12, int(w * FONT_SCALE))
        font_size_variant = max(10, int(w * VARIANT_SCALE))
        line_gap          = int(h * LINE_GAP_RATIO)

        store_font   = self._get_font(font_size_store)
        variant_font = self._get_font(font_size_variant)

        store_label   = STORE_NAME
        variant_label = VARIANT_LABELS.get(variant, variant)

        # Measure text
        sb = draw.textbbox((0, 0), store_label,   font=store_font)
        vb = draw.textbbox((0, 0), variant_label, font=variant_font)
        s_w, s_h = sb[2] - sb[0], sb[3] - sb[1]
        v_w, v_h = vb[2] - vb[0], vb[3] - vb[1]

        total_text_h = s_h + line_gap + v_h

        # Vertical centre within art box
        block_top = art_mid_y - total_text_h // 2

        # Horizontal centre
        s_x = (w - s_w) // 2
        v_x = (w - v_w) // 2
        s_y = block_top
        v_y = block_top + s_h + line_gap

        # Alpha value from opacity
        alpha = int(255 * opacity)

        # Optional: faint bounding box inside art zone for legibility
        pad = 12
        box_left   = max(8, min(s_x, v_x) - pad)
        box_right  = min(w - 8, max(s_x + s_w, v_x + v_w) + pad)
        box_top    = max(art_top + 4, s_y - pad)
        box_bottom = min(art_bottom - 4, v_y + v_h + pad)
        box_alpha  = int(alpha * 0.35)   # lighter than text

        draw.rounded_rectangle(
            [box_left, box_top, box_right, box_bottom],
            radius=6,
            fill=(0, 0, 0, box_alpha),
        )

        # Draw store name
        draw.text((s_x, s_y), store_label,   font=store_font,
                  fill=(*TEXT_COLOR, alpha))
        # Draw variant label slightly dimmer
        draw.text((v_x, v_y), variant_label, font=variant_font,
                  fill=(*TEXT_COLOR, int(alpha * 0.80)))

        # ── Clip overlay to art-box rows only ────────────────────────────────
        # Anything outside the art zone is blanked (alpha → 0)
        art_mask = Image.new("L", (w, h), 0)
        art_mask.paste(255, (0, art_top, w, art_bottom))

        # Apply mask: pixels outside art zone become transparent
        r, g, b, a = overlay.split()
        a = Image.fromarray(
            __import__("PIL.ImageChops", fromlist=["multiply"]).multiply(a, art_mask).tobytes(),
            "L"
        )
        overlay = Image.merge("RGBA", (r, g, b, a))

        # Composite onto original
        result = Image.alpha_composite(img, overlay)

        # Save as PNG (preserves transparency if original had it)
        result.convert("RGB").save(out_file, "PNG", optimize=True)

    def _get_font(self, size):
        """Load a font — falls back gracefully if none available."""
        # Try common system font paths
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        # PIL built-in bitmap font as last resort
        return ImageFont.load_default()
