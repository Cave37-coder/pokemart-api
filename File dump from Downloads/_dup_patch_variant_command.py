"""
Run from your project root to patch generate_variant_images with fixed Pillow handling.

    cd C:\\Users\\texca\\pokemart-api
    python patch_variant_command.py
"""

import os

PATH = os.path.join("products", "management", "commands", "generate_variant_images.py")

CONTENT = '''"""
Management command: generate_variant_images
============================================
Reads clean originals from media/card_images/originals/
and generates a watermarked copy for every non-Normal PokemonProduct.
Watermark is confined strictly to the art-box zone of the card.

Usage:
    python manage.py generate_variant_images
    python manage.py generate_variant_images --set sv3pt5
    python manage.py generate_variant_images --force
    python manage.py generate_variant_images --opacity 0.18
    python manage.py generate_variant_images --test SCR 1

Output:
    media/card_images/variants/{set_code}/{card_number}_{variant}.png

Requires:
    pip install --upgrade Pillow --break-system-packages
"""

import os, io
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

try:
    from PIL import Image, ImageDraw, ImageFont, ImageChops
    PILLOW_OK = True
    PILLOW_VER = getattr(Image, "__version__", "unknown")
except ImportError:
    PILLOW_OK = False
    PILLOW_VER = "not installed"

NO_OVERLAY = {"N", "DR"}

# Card zone ratios (fraction of total card height)
ART_TOP_RATIO    = 0.115
ART_BOTTOM_RATIO = 0.620

STORE_NAME     = "PokeBulk SA"   # ASCII only — avoids font encoding issues
TEXT_COLOR     = (255, 255, 255)
FONT_SCALE     = 0.055
VARIANT_SCALE  = 0.040
LINE_GAP_RATIO = 0.015

VARIANT_LABELS = {
    "H":      "Holofoil",
    "RH":     "Reverse Holo",
    "ERH":    "ETB Reverse Holo",
    "RH-PB":  "Poke Ball Holo",
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
    "SIR":    "Special Illus. Rare",
    "HR":     "Hyper Rare",
}


class Command(BaseCommand):
    help = "Generate watermarked variant images from clean card originals"

    def add_arguments(self, parser):
        parser.add_argument("--set",     dest="set_code")
        parser.add_argument("--force",   action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--opacity", type=float, default=0.17)
        parser.add_argument("--test",    nargs=2, metavar=("SET", "NUM"),
                            help="Test a single card e.g. --test SCR 1")

    def handle(self, *args, **options):
        if not PILLOW_OK:
            self.stderr.write(self.style.ERROR(
                "Pillow not installed.\\n"
                "Run: pip install --upgrade Pillow --break-system-packages"
            ))
            return

        self.stdout.write(f"Pillow version: {PILLOW_VER}")

        from products.models import PokemonProduct

        set_filter = options["set_code"]
        force      = options["force"]
        dry_run    = options["dry_run"]
        opacity    = max(0.05, min(0.40, options["opacity"]))
        test_args  = options.get("test")

        orig_base    = Path(settings.MEDIA_ROOT) / "card_images" / "originals"
        variant_base = Path(settings.MEDIA_ROOT) / "card_images" / "variants"
        variant_base.mkdir(parents=True, exist_ok=True)

        # ── Test mode: stamp one card and open it ────────────────────────────
        if test_args:
            sc, num = test_args
            orig = orig_base / sc / f"{num}.png"
            if not orig.exists():
                self.stderr.write(self.style.ERROR(f"Original not found: {orig}"))
                return
            out_dir  = variant_base / sc
            out_file = out_dir / f"{num}_TEST_RH.png"
            self.stdout.write(f"Test stamping: {orig} → {out_file}")
            try:
                self._stamp(orig, out_dir, out_file, "RH", opacity)
                self.stdout.write(self.style.SUCCESS(f"Success! Check: {out_file}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed: {e}"))
                import traceback; traceback.print_exc()
            return

        # ── Normal batch mode ────────────────────────────────────────────────
        qs = PokemonProduct.objects.select_related("card_set").all()
        if set_filter:
            qs = qs.filter(card_set__code=set_filter)
        qs = qs.exclude(variant_override__in=list(NO_OVERLAY) + ["", None])

        total, done, skipped, missing = qs.count(), 0, 0, []

        self.stdout.write(self.style.HTTP_INFO(
            f"\\n{\'[DRY RUN] \' if dry_run else \'\'}Processing {total} variant products "
            f"(opacity={opacity})\\n"
        ))

        for product in qs:
            sc      = product.card_set.code if product.card_set else None
            num     = product.card_number
            variant = product.variant_override

            if not sc or not num or not variant:
                continue

            orig = orig_base / sc / f"{num}.png"
            if not orig.exists():
                missing.append(f"{sc}/{num}")
                continue

            safe_v   = variant.replace("/", "-").replace("\\\\", "-")
            out_dir  = variant_base / sc
            out_file = out_dir / f"{num}_{safe_v}.png"

            if out_file.exists() and not force:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY] {sc}/{num}_{safe_v}.png  "
                    f"[{VARIANT_LABELS.get(variant, variant)}]"
                )
                done += 1
                continue

            try:
                self._stamp(orig, out_dir, out_file, variant, opacity)
                done += 1
                self.stdout.write(f"  ✓ {sc}/{num}_{safe_v}.png")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ✗ {sc}/{num}: {e}"))

        self.stdout.write("\\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Generated : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Skipped   : {skipped}"))
        if missing:
            um = sorted(set(missing))
            self.stdout.write(self.style.WARNING(
                f"  No orig   : {len(um)} (run download_card_images first)"
            ))
            for m in um[:15]:
                self.stdout.write(f"    - {m}")
            if len(um) > 15:
                self.stdout.write(f"    ... +{len(um)-15} more")
        self.stdout.write("─" * 50 + "\\n")

    # ── Core overlay logic ────────────────────────────────────────────────────

    def _stamp(self, orig_file, out_dir, out_file, variant, opacity):
        out_dir.mkdir(parents=True, exist_ok=True)

        # Read file bytes explicitly, then wrap in BytesIO
        # This avoids the 'bytes has no __array_interface__' bug on Python 3.14
        raw = orig_file.read_bytes()
        img = Image.open(io.BytesIO(raw))

        # Force convert to RGB first, then RGBA — more compatible on all Pillow versions
        if img.mode == "P":
            img = img.convert("RGBA")
        elif img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        img = img.convert("RGBA")
        w, h = img.size

        art_top    = int(h * ART_TOP_RATIO)
        art_bottom = int(h * ART_BOTTOM_RATIO)
        art_h      = art_bottom - art_top
        art_mid_y  = art_top + art_h // 2

        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        fs_store   = max(12, int(w * FONT_SCALE))
        fs_variant = max(10, int(w * VARIANT_SCALE))
        gap        = int(h * LINE_GAP_RATIO)

        sfont = self._font(fs_store)
        vfont = self._font(fs_variant)

        slabel = STORE_NAME
        vlabel = VARIANT_LABELS.get(variant, variant)

        sb = draw.textbbox((0, 0), slabel, font=sfont)
        vb = draw.textbbox((0, 0), vlabel, font=vfont)
        sw, sh = sb[2]-sb[0], sb[3]-sb[1]
        vw, vh = vb[2]-vb[0], vb[3]-vb[1]

        block_top = art_mid_y - (sh + gap + vh) // 2
        sx = (w - sw) // 2
        vx = (w - vw) // 2
        sy = block_top
        vy = block_top + sh + gap

        alpha     = int(255 * opacity)
        box_alpha = int(alpha * 0.35)
        pad       = 12

        # Clamp box to art zone
        bx1 = max(8, min(sx, vx) - pad)
        by1 = max(art_top + 4, sy - pad)
        bx2 = min(w - 8, max(sx + sw, vx + vw) + pad)
        by2 = min(art_bottom - 4, vy + vh + pad)

        draw.rounded_rectangle([bx1, by1, bx2, by2], radius=6,
                               fill=(0, 0, 0, box_alpha))
        draw.text((sx, sy), slabel, font=sfont,
                  fill=(*TEXT_COLOR, alpha))
        draw.text((vx, vy), vlabel, font=vfont,
                  fill=(*TEXT_COLOR, int(alpha * 0.82)))

        # Clip overlay to art zone only
        mask = Image.new("L", (w, h), 0)
        mask.paste(255, (0, art_top, w, art_bottom))

        r, g, b, a = overlay.split()
        a = ImageChops.multiply(a, mask)
        overlay = Image.merge("RGBA", (r, g, b, a))

        result = Image.alpha_composite(img, overlay)

        # Save as RGB PNG
        result.convert("RGB").save(str(out_file), format="PNG", optimize=True)

    def _font(self, size):
        candidates = [
            # Windows
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/verdanab.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
        return ImageFont.load_default()
'''

with open(PATH, "w", encoding="utf-8") as fh:
    fh.write(CONTENT)

print(f"✓ Patched: {PATH}")
print()
print("Now test it with a single card first:")
print("  python manage.py generate_variant_images --test SCR 1")
print()
print("If that works, run the full batch:")
print("  python manage.py generate_variant_images")
print()
print("Also restart the download to pick up what failed:")
print("  python manage.py download_card_images")
